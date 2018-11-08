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

    def color_message(self, color, message, end_line=True):
        if end_line:
            print color + str(message) + self.ENDC
        else:
            print color + str(message),



class Tracker():
    def __init__(self, tracker_size,
            verbose=True, debug=False,
            calibration_patience=int(1e3)
        ):
        self.verbose = verbose
        self.debugging = debug
        self.logger = bcolors()

        self.tracker_size = tracker_size

        ''' instantiate state represetation as invalid '''
        self.calibration_state = None
        self.current_state = None

        '''  '''
        self.ask_counter = 0
        self.calibration_patience = calibration_patience

    def calibrated(self):
        return not (self.calibration_state is None)

    def valid_state(self, sources):
        """
        Tells if the tracker should attempt to
            calibrate or keep tracking the detected sources

        A false return will eventually uncalibrate the system!
        """
        return len(sources) >= self.tracker_size

    def outlier_removal(self, sources):
        return sources[:self.tracker_size]

    def state_dict(self, sources):
        """ Assumptions:
        - sources is a valid state

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

    def calibrate(self, sources):
        """ Assumptions:
        - sources is a valid state

        Wrapper for building calibration_state from scratch
        Also updates current_state since this is a system recovery
        """
        self.calibration_state = self.state_dict(sources)
        self.current_state = self.calibration_state

    def lose_track(self):
        if self.verbose:
            self.logger.color_message(bcolors.FAIL, "Lost track!")
        self.calibration_state = None
        self.ask_counter = 0

    def track_sources(self, sources):
        """ Assumptions:
        - instance is calibrated
        - sources is a valid state
        - outlier removal was done (otherwise tracking is impossible)

        Returns a current_state update
        """

        if self.debugging:
            assert self.calibrated()
            assert self.current_state is not None
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
                    self.current_state.items()
                ))

                t = sorted(t, key = lambda x: x[1])

                best = t[0][0]

                if tracked.has_key(best):
                    """  any outlier removal should have been done already ;
                        tracking is a bijection """
                    raise ValueError
                else:
                    if self.debugging:
                        self.logger.color_message(bcolors.OKBLUE, "Matching point %d-th point %s to %s" % (i, str(s), best))
                    tracked[best] = s

            if self.debugging:
                """ the logic should never allow the assert below to fail """
                try:
                    assert len(tracked) == self.tracker_size
                except:
                    print "Sources: ", sources
                    self.logger.color_message(bcolors.FAIL, ("Failed trying to match %d-th point (%s) to %s but \
                        its value is %s" % (i, str(s), best, tracked[best])))
                    exit()

            return tracked

        except ValueError:
            """ could not associate
            since we have a valid detection, calibrate
            """
            self.logger.color_message(bcolors.OKGREEN, "Recalibrating")
            self.calibrate(sources)
            return self.current_state

    def log(self, sources, time):
        valid_src = False
        for src in sources:
            if src:
                valid_src = True
                self.logger.color_message(bcolors.OKBLUE, str(src['pos']), end_line=False)

        if valid_src:
            print '' + bcolors.ENDC


    def receive(self, sources, time):
        """
        [ DEVELOPMENT
            ok this fucking needs a refactor haHAA
            nasty flow control
        ]
        """
        sources = list(filter(lambda x: x is not None, sources))
        valid = self.valid_state(sources)

        if self.verbose:
            self.log(sources, time)
            if self.current_state:
                print self.current_state


        if not valid:
            if not self.calibrated():
                if self.ask_counter == 0:
                    self.logger.color_message(bcolors.WARNING, "Waiting for calibration trigger")
                self.ask_counter = (self.ask_counter + 1) % self.calibration_patience

            else:
                self.lose_track()
                self.current_state = None
        else:
            if not self.calibrated():
                self.logger.color_message(bcolors.OKGREEN, "Calibrating")

                self.calibrate(sources)
            else:
                self.current_state = self.track_sources(
                    self.outlier_removal(sources)
                )
