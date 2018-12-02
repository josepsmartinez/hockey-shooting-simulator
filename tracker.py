from math import cos, sin, acos

import copy
from datetime import datetime

import cwiid

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def __init__(self):
        self.logfile = None
        self.logtimestamp = None

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''

    def disk(self, message, end_line=True):
        if self.logfile is not None:
            self.logfile.write(str(message))

            if end_line:
                self.logfile.write('\n')

    def _color_message(self, color, message, end_line=True, skip_disk=False):
        if not skip_disk:
            self.disk(message)

        if end_line:
            print color + str(message) + self.ENDC
        else:
            print color + str(message),

    def warning(self, message, **kwargs):
        self._color_message(self.WARNING, message, skip_disk=True, **kwargs)

    def error(self, message, **kwargs):
        self._color_message(self.FAIL, message, **kwargs)

    def green(self, message, **kwargs):
        self._color_message(self.OKGREEN, message, **kwargs)

    def blue(self, message, **kwargs):
        self._color_message(self.OKBLUE, message, skip_disk=True, **kwargs)



class Tracker():
    def __init__(self, tracker_size,
        trigger_index,
        puck_position, puck_proximity=10,
        camera_rotation=0,
        verbose=True, debug=False,
        calibration_patience=int(1e3),
        tracking_patience=int(1e2)
        ):
        self.logger = bcolors()


        """ instantiate state represetation as invalid """
        self.state = 'U'
        self.current_sources = []
        self.calibration_snapshot = None
        self.current_snapshot = None

        self.touching_point = None

        self.last_tracking_status = 'NACK'

        """ config """
        self.tracker_size = tracker_size
        self.trigger_index = trigger_index

        self.puck_position = puck_position
        self.shooting_line = puck_position[1] - cwiid.IR_Y_MAX*0.1
        self.puck_proximity = puck_proximity

        self.camera_rotation = camera_rotation

        self.verbose = verbose
        self.debugging = debug

        self.calibration_patience = calibration_patience
        self.tracking_patience = tracking_patience

        """  """
        self.ask_counter = 0
        self.lose_counter = 0

        self.shoot_counter = 0

    """ Actions """
    def _calibrate(self, sources):
        """ Assumptions:
        - sources is a valid and calibration snapshot

        Wrapper for building calibration_snapshot from scratch
        Also updates current_snapshot since this is a system recovery
        """
        self.state = 'W'
        self.lose_counter = 0

        self.calibration_snapshot = self.state_dict(sources)
        self.current_snapshot = copy.deepcopy(self.calibration_snapshot)

    def _start_shoot(self):
        self.logger.green("Shoot started")
        self.state = 'S'

    def _end_shoot(self):
        self.logger.green("Shoot ended")
        self.shoot_counter += 1
        #self.state = 'W'
        self.state = 'U'

    def _lose_track(self):
        if self.verbose:
            self.logger.error("Lost track!")

        self.calibration_snapshot = None
        self.touching_point = None

        self.state = 'U'
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

        tracked = {}
        added_keys = []

        for k, v in self.current_snapshot.items():
            print(sources)
            print(v)
            """ builds a list of (point_id, distance) so
            we can compute the match source to its closest point """
            t = list(map(
                lambda (i,s): (i,
                    (s['pos'][0]-v['pos'][0])**2 +
                    (s['pos'][1]-v['pos'][1])**2),
                enumerate(sources)
            ))

            t = sorted(t, key = lambda x: x[1])

            best = t[0][0] # sources index

            if best in added_keys:
                """ stalemate: detected source is equidistant to multiple tracked ones """
                self.logger.warning("stalemate")
                pass
            else:
                self.logger.blue("Matching point %d-th point %s to %s" % (k, str(v), str(sources[best])))
                tracked[k] = sources[best]
                added_keys.append(best)

        if self.debugging:
            """ the logic should never allow the assert below to fail """
            try:
                assert len(tracked) == self.tracker_size
            except:
                print "Sources: ", sources
                self.logger.warning("Failed trying to match %d-th point (%s) to %s but \
                    its value is %s" % (i, str(s), best, tracked[best]))
                exit()

        print(self.logger.blue("Tracking %d points!!" % len(tracked.keys())))

        if (len(tracked.keys()) < self.tracker_size):
            return None
        else:
            return tracked


    """ Interface """
    def receive(self, sources, time):
        """
        """
        sources = self.sources_preprocess(sources)
        self.current_sources = sources

        valid = self.is_valid_snapshot(sources)
        could_track = False


        calibration_moment = self.is_calibration_snapshot(sources) if valid else False

        if calibration_moment:
            """ excludes trigger """
            sources.sort(key=lambda x: x['pos'][1])
            print("EXCLUDING TRIGGER SOURCES", sources)
            sources = sources[:self.trigger_index] + sources[1+self.trigger_index:]

        if self.state == 'U':
            if calibration_moment and valid:
                self.logger.green("Calibrating")
                self._calibrate(sources)

            else:
                if self.ask_counter == 0:
                    self.logger.warning("Waiting for calibration trigger")
                self.ask_counter = (self.ask_counter + 1) % self.calibration_patience

        else:
            if valid:
                """ attemps tracking """
                tracking_results = self._track_sources(sources)
                could_track = tracking_results is not None

            if could_track:
                self.lose_counter = 0
                self.current_snapshot = tracking_results

                #sources = [v for (k,v) in self.current_snapshot.items()]

                """ shooting stats
                   note it only gets updated when tracking is sucessful!
                   a delayed state is held on .current_snapshot until
                    - detected sources are succesfully mapped to .current_snapshot, or
                    - tracking patience is over
                """
                self.update_touching_point()

                shooting = self.performing_shoot() if valid else False
                touching_puck = self.starting_shoot() if valid else False

                """ shoot detection """
                if self.state == 'S' and not shooting:
                    self._end_shoot()

                elif self.state == 'W' and touching_puck:
                    self._start_shoot()

            else:
                """ tracking patience """
                self.lose_counter += 1

                self.logger.warning("%s : %s" % (self.lose_counter, str(sources)))

                if self.lose_counter >= self.tracking_patience:
                    if self.state == 'S':
                        self._end_shoot()
                    self._lose_track()
                    self.current_snapshot = None


        self.last_tracking_status = could_track

        """ stdout logging """
        if self.verbose:

            if self.state != 'U':
                self.log(sources, time)

            if self.current_snapshot:
                print "current_snapshot [%s]: %s" % (self.state, self.current_snapshot)

            #print "raw_sources: %s" % (self.current_sources)

    def reset_shoot_counter(self):
        self.shoot_counter = 0

    def set_logging_point(self, logging_point):
        self.logger.logfile = logging_point
        self.logger.logtimestamp = datetime.now()

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

    def update_touching_point(self):
        def next_point(p0, p1, s=1.0):
            return p1

        #self.touching_point = next_point(self.current_snapshot[0]['pos'], self.current_snapshot[1]['pos'], s=1.0)
        self.touching_point = self.current_snapshot[1]['pos']

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

    def starting_shoot(self):
        """
        Assumptions:

        Tells if lowest stick point is touching virtual puck location
        """

        condition = (
            (self.touching_point[0] - self.puck_position[0])**2 +
            (self.touching_point[1] - self.puck_position[1])**2
        ) <= self.puck_proximity**2 if self.touching_point else False

        #print "Condition: ", condition

        return condition

    def performing_shoot(self):
        """
        Assumptions:
        - current tracker state is Shooting

        Tells if shoot is still being performed
        """

        condition = self.touching_point[1] > self.shooting_line if self.touching_point else False

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
        return { i:v for (i,v) in enumerate(sorted(sources, key=lambda x: x['pos'][1])) }

    """ I/O """
    def log(self, sources, time):
        """ STDOUT """
        valid_src = False
        self.logger.blue(self.state + ' ', end_line=False)
        for src in sources:
            if src:
                valid_src = True
                self.logger.blue(str(src['pos']), end_line=False)

                self.logger.blue(' ' + str(src['size']), end_line=False)

        if valid_src:
            print '' + bcolors.ENDC

        """ DISK """
        self.disk_state_dump() # ends line

    def disk_state_dump(self):
        """
        Renders current_snapshot (if any) as a 3D line in a text file
        """
        if self.current_snapshot is not None:
            # ESTIMATE Z-COORDINATE
            calibration_distance = (self.calibration_snapshot[0]['pos'][0] - self.calibration_snapshot[1]['pos'][0]) ** 2
            calibration_distance+= (self.calibration_snapshot[0]['pos'][1] - self.calibration_snapshot[1]['pos'][1]) ** 2

            current_distance = (self.current_snapshot[0]['pos'][0] - self.current_snapshot[1]['pos'][0]) ** 2
            current_distance+= (self.current_snapshot[0]['pos'][1] - self.current_snapshot[1]['pos'][1]) ** 2

            z_estim = max(0, (calibration_distance - current_distance)) ** (0.5)

            '''
            print("Z-COORDINATE", self.calibration_snapshot, self.current_snapshot)
            print("Z distances %f %f %f" % (calibration_distance, current_distance, z_estim))
            '''

            dump = list(map(lambda (k,x): list(x['pos']) + [0 if k==0 else z_estim], self.current_snapshot.items()))

            dump_str = ''.join(map(lambda x: "%d %d %d " % (x[0], x[1], x[2]), dump))
            #dump_str += '\n'

            self.logger.disk(dump_str)
        else:
            pass
            #print("No snapshot available",
            #    "Tracker state: %s" % self.state)
