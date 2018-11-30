from math import cos, sin, acos

import cwiid

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''

    def _color_message(self, color, message, end_line=True):
        if end_line:
            print color + str(message) + self.ENDC
        else:
            print color + str(message),

    def warning(self, message, **kwargs):
        self._color_message(self.WARNING, message, **kwargs)

    def error(self, message, **kwargs):
        self._color_message(self.FAIL, message, **kwargs)

    def green(self, message, **kwargs):
        self._color_message(self.OKGREEN, message, **kwargs)

    def blue(self, message, **kwargs):
        self._color_message(self.OKBLUE, message, **kwargs)



class Tracker():
    def __init__(self, tracker_size,
        trigger_index,
        puck_position, puck_proximity=10,
        camera_rotation=0,
        verbose=True, debug=False,
        calibration_patience=int(1e3),
        tracking_patience=10
        ):
        self.logger = bcolors()

        """ instantiate state represetation as invalid """
        self.state = 'U'
        self.current_sources = []
        self.calibration_snapshot = None
        self.current_snapshot = None

        """ config """
        self.tracker_size = tracker_size
        self.trigger_index = trigger_index

        self.puck_position = puck_position
        self.puck_proximity = puck_proximity

        self.camera_rotation = camera_rotation

        self.verbose = verbose
        self.debugging = debug

        self.calibration_patience = calibration_patience
        self.tracking_patience = tracking_patience

        """  """
        self.ask_counter = 0
        self.lose_counter = 0

    """ Actions """
    def _calibrate(self, sources):
        """ Assumptions:
        - sources is a valid and calibration snapshot

        Wrapper for building calibration_snapshot from scratch
        Also updates current_snapshot since this is a system recovery
        """
        self.state = 'W'
        self.calibration_snapshot = self.state_dict(sources)
        self.current_snapshot = self.calibration_snapshot

    def _start_shoot(self):
        self.logger.green("Shoot started")
        self.state = 'S'

    def _end_shoot(self):
        self.logger.green("Shoot ended")
        self.state = 'W'

    def _lose_track(self):
        if self.verbose:
            self.logger.error("Lost track!")

        self.state = 'U'
        self.calibration_snapshot = None
        self.ask_counter = 0

    def _track_sources(self, sources):
        """ Assumptions:
        - instance is calibrated
        - sources is a valid snapshot

        Returns a current_snapshot update
        """

        if self.debugging:
            assert self.current_snapshot is not None
            assert len(sources) == self.tracker_size

        try:
            tracked = {}

            for i, (k,v) in enumerate(self.current_snapshot.items()):
                print(sources)
                print(v)
                """ builds a list of (point_id, distance) so
                we can compute the match source to its closest point """
                t = list(map(
                    lambda s: (k,
                        (s['pos'][0]-v['pos'][0])**2 +
                        (s['pos'][1]-v['pos'][1])**2),
                    sources
                ))

                t = sorted(t, key = lambda x: x[1])

                best = t[0][0]

                if tracked.has_key(best):
                    """ stalemate: detected source is equidistant to multiple tracked ones """
                    pass
                else:
                    if self.debugging:
                        self.logger.blue("Matching point %d-th point %s to %s" % (i, str(s), best))
                    tracked[best] = v

            if self.debugging:
                """ the logic should never allow the assert below to fail """
                try:
                    assert len(tracked) == self.tracker_size
                except:
                    print "Sources: ", sources
                    self.logger.error("Failed trying to match %d-th point (%s) to %s but \
                        its value is %s" % (i, str(s), best, tracked[best]))
                    exit()

            return tracked

        except ValueError:
            """ could not associate
            since we have a valid detection, calibrate
            """
            self.logger.green("Recalibrating")
            self._calibrate(sources)
            return self.current_snapshot

    """ Interface """
    def receive(self, sources, time):
        """
        """
        sources = self.sources_preprocess(sources)
        self.current_sources = sources

        valid = self.is_valid_snapshot(sources)

        if self.state == 'U':
            calibration_moment = self.is_calibration_snapshot(sources) if valid else False

            if calibration_moment:
                self.logger.green("Calibrating")

                """ excludes trigger """
                sources.sort(key=lambda x: x['pos'][1])
                sources = sources[:self.trigger_index] + sources[1+self.trigger_index:]

                self._calibrate(sources)

            else:
                if self.ask_counter == 0:
                    self.logger.warning("Waiting for calibration trigger")
                self.ask_counter = (self.ask_counter + 1) % self.calibration_patience

        else:
            if valid:
                """ tracking """
                self.current_snapshot = self._track_sources(sources)
                sources = [v for (k,v) in self.current_snapshot.items()]

                shooting = self.performing_shoot(sources) if valid else False
                touching_puck = self.starting_shoot(sources) if valid else False

                """ shoot detection """
                if self.state == 'S' and not shooting:
                    self._end_shoot()

                elif self.state == 'W' and touching_puck:
                    self._start_shoot()
            else:
                """ tracking patience """
                self.lose_counter += 1

                self.logger.error("%s : %s" % (self.lose_counter, str(sources)))

                if self.lose_counter >= self.tracking_patience:
                    self._lose_track()
                    self.current_snapshot = None


        """ stdout logging """
        if self.verbose:
            if self.state != 'U':
                self.log(sources, time)

            if self.current_snapshot:
                print "[%s]: %s" % (self.state, self.current_snapshot)

    """ Internal Methods """
    def sources_preprocess(self, sources):
        """
        Filter and map functions for raw sources
        """
        sources = list(filter(lambda x: x is not None, sources))

        def rotate_point(p,a,o):
            p = (p[0]-o[0], p[1]-o[1])
            a = (a%360) * acos(-1) / 180.0
            return (
                int(o[0] + cos(a) * p[0] - sin(a) * p[1]),
                int(o[1] + cos(a) * p[1] + sin(a) * p[0]),
            )

        sources = list(map(lambda x: {
            'pos': rotate_point(x['pos'],
                    self.camera_rotation, (cwiid.IR_X_MAX//2, cwiid.IR_Y_MAX//2)
                    ),
            'size': x['size']
        }, sources))

        return sources

    def is_valid_snapshot(self, sources):
        """
        Tells if the tracker should attempt to
            calibrate or keep tracking the detected sources

        A false return will eventually uncalibrate the system!
        """
        return len(sources) >= self.tracker_size

    def is_calibration_snapshot(self, sources):
        """
        """
        horizontal_proximity = int(1e2)
        trigger_index = 1 + self.tracker_size//2

        if len(sources) == (1 + self.tracker_size):
            horizontal_mean = sum(map(lambda x: x['pos'][0], sources)) / float(len(sources))
            horizontal_diffs = list(map(lambda x: (x['pos'][0] - horizontal_mean)**2, sources))

            # debug print
            for i in range(len(sources)):
                print(sources[i], horizontal_mean, horizontal_diffs[i])

            if all(map(lambda x: x <= horizontal_proximity**2, horizontal_diffs)):
                return True

            else:
                self.logger.warning("At least one detected point is too far from axis")
        else:
            if len(sources) != self.tracker_size:
                self.logger.warning("Too much (%d) sources detected" % (len(sources)))

        return False

    def starting_shoot(self, sources):
        """
        Assumptions:
        - source is a valid snapshot

        Tells if lowest stick point is touching virtual puck location
        """
        #print "Raw sources", sources
        sources.sort(key=lambda x: x['pos'][1])
        print "Ordered sources", sources

        condition = (
            (sources[0]['pos'][0] - self.puck_position[0])**2 +
            (sources[0]['pos'][1] - self.puck_position[1])**2
        ) <= self.puck_proximity**2

        print "Condition: ", condition

        return condition

    def performing_shoot(self, sources):
        """
        Assumptions:
        - source is a valid snapshot
        - current tracker state is Shooting

        Tells if shoot is still being performed
        """
        sources.sort(key=lambda x: x['pos'][1])

        condition = sources[0]['pos'][1] > (self.puck_position[1] - cwiid.IR_Y_MAX*0.2)

        return condition

    def state_dict(self, sources):
        """ Assumptions:
        - sources is a valid snapshot

        Behavior:
            Builds a dictionary so any tracked point is identified
            Tracking process is essentially updating this dictionary
                in a way any value comes from detected sources

        [ DEVELOPMENT
        This is the point for dealing with
            the ambiguity caused by rotation symmetry

        Levels of solutions:
            - 0: be constant from calibration to fail
            - 1: be constant during a single run
            - 2: relate to the same physical IR source (constant always)

        Pros
            - drawing implementation is easier,
                any line could be rendered independently
            - shooting detection is easier,
                just look at the key that represents the bottom IR source

        Cons
            - not implemented (haHA)
            - slows tracking process -> lower FPS

        Current implementation provides a level 0 solution

        ]
        """
        return { i:v for (i,v) in enumerate(sources) }

    """ I/O """
    def log(self, sources, time):
        valid_src = False
        self.logger.blue(self.state + ' ', end_line=False)
        for src in sources:
            if src:
                valid_src = True
                self.logger.blue(str(src['pos']), end_line=False)

                self.logger.blue(' ' + str(src['size']), end_line=False)

        if valid_src:
            print '' + bcolors.ENDC
