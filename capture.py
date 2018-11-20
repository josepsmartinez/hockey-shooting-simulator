import cwiid
wiimote = None

from tracker import Tracker

POINTS_TO_BE_TRACKED = 1

def get_wiimote():
    global wiimote
    print("Looking for Wiimote \n Put it in discoverable mode (sync button) then press 1+2 ...")
    wiimote = cwiid.Wiimote()

    # defaults
    rumble=0
    rpt_mode=0 ; rpt_mode ^= cwiid.RPT_IR
    led = 0 ; led ^= cwiid.LED3_ON

    wiimote.rumble = rumble
    wiimote.rpt_mode = rpt_mode
    wiimote.led = led
    wiimote.enable(cwiid.FLAG_MESG_IFC);

    return wiimote

def high_callback(ir_callback):
    def cb(mesg_list, time):
        for mesg in mesg_list:
            if mesg[0] == cwiid.MESG_IR:
                ir_callback(mesg, time)

            elif mesg[0] ==  cwiid.MESG_ERROR:
                print "Error message received"
                global wiimote
                wiimote.close()
                exit(-1)
            else:
                print 'Unknown Report'
    return cb

def main():
    get_wiimote()

    global wiimote

    tracker = Tracker(POINTS_TO_BE_TRACKED)

    wiimote.mesg_callback = high_callback(lambda mesg, time: tracker.receive(mesg[1], time))

    print("wiimote pegadinho")

    ''' 'infinite' loop just to keep connection alive, callback handles data '''
    while 1:
        pass

if __name__ == '__main__':
    main()
