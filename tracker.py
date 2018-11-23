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
            puck_position, puck_proximity=10,
            verbose=True, debug=False,
            calibration_patience=int(1e3)
        ):
        self.logger = bcolors()

        ''' instantiate state represetation as invalid '''
        self.state = 'U'
        self.current_sources = []
        self.calibration_snapshot = None
        self.current_snapshot = None

        ''' config '''
        self.tracker_size = tracker_size
        self.puck_position = puck_position
        self.puck_proximity = puck_proximity

        self.verbose = verbose
        self.debugging = debug
        self.calibration_patience = calibration_patience

        '''  '''
        self.ask_counter = 0

    """ Actions """
    def calibrate(self, sources):
        """ Assumptions:
        - sources is a valid snapshot

        Wrapper for building calibration_snapshot from scratch
        Also updates current_snapshot since this is a system recovery
        """
        self.state = 'W'
        self.calibration_snapshot = self.state_dict(sources)
        self.current_snapshot = self.calibration_snapshot

    def start_shoot(self):
        self.logger.green("Shoot started")
        self.state = 'S'

    def end_shoot(self):
        self.logger.green("Shoot ended")
        self.state = 'W'

    def lose_track(self):
        if self.verbose:
            self.logger.error("Lost track!")

        self.state = 'U'
        self.calibration_snapshot = None
        self.ask_counter = 0

    def track_sources(self, sources):
        """ Assumptions:
        - instance is calibrated
        - sources is a valid snapshot
        - outlier removal was done (otherwise tracking is impossible)

        Returns a current_snapshot update
        """

        if self.debugging:
            assert self.calibrated()
            assert self.current_snapshot is not None
            assert len(sources) == self.tracker_size

        try:
            tracked = {}
            for i, s in enumerate(sources):
                """ builds a list of (point_id, distance) so
                we can compute the match source to its closest point """
                t = list(map(
                    lambda (k,v): (k,
                        (s['pos'][0]-v['pos'][0])**2 +
                        (s['pos'][1]-v['pos'][1])**2),
                    self.current_snapshot.items()
                ))

                t = sorted(t, key = lambda x: x[1])

                best = t[0][0]

                if tracked.has_key(best):
                    """  any outlier removal should have been done already ;
                        tracking is a bijection """
                    raise ValueError
                else:
                    if self.debugging:
                        self.logger.blue("Matching point %d-th point %s to %s" % (i, str(s), best))
                    tracked[best] = s

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
            self.calibrate(sources)
            return self.current_snapshot

    """ Interface """
    def receive(self, sources, time):
        """
        [ DEVELOPMENT
            ok this fucking needs a refactor haHAA
            nasty flow control
        ]
        """
        sources = list(filter(lambda x: x is not None, sources))
        valid = self.valid_snapshot(sources)
        shooting = self.performing_shoot(sources) if valid else False
        touching_puck = self.starting_shoot(sources) if valid and not shooting else False

        self.current_sources = sources

        """ shoot detection """
        if self.state == 'S' and not shooting:
            self.end_shoot()

        elif self.state == 'W' and (touching_puck or shooting):
            self.start_shoot()

        """ tracking """
        if self.state == 'U':
            if valid:
                self.logger.green("Calibrating")
                self.calibrate(sources)
            else:
                if self.ask_counter == 0:
                    self.logger.warning("Waiting for calibration trigger")
                self.ask_counter = (self.ask_counter + 1) % self.calibration_patience

        else:
            if valid:
                fit_sources = self.outlier_removal(sources)
                self.current_snapshot = self.track_sources(fit_sources)
            else:
                self.lose_track()
                self.current_snapshot = None


        """ stdout logging """
        if self.verbose:
            self.log(sources, time)
            if self.current_snapshot:
                print "[%s]: %s" % (self.state, self.current_snapshot)

    """ Internal Methods """
    def valid_snapshot(self, sources):
        """
        Tells if the tracker should attempt to
            calibrate or keep tracking the detected sources

        A false return will eventually uncalibrate the system!
        """
        return len(sources) >= self.tracker_size


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

        condition = sources[0]['pos'][1] > cwiid.IR_Y_MAX*0.2

        return condition

    def outlier_removal(self, sources):
        return sources[:self.tracker_size]

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
        return { i:v for (i,v) in enumerate(self.outlier_removal(sources)) }

    def log(self, sources, time):
        valid_src = False
        for src in sources:
            if src:
                valid_src = True
                self.logger.blue(str(src['pos']), end_line=False)

        if valid_src:
            print '' + bcolors.ENDC
