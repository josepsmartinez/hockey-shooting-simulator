import cwiid

from tracker import Tracker

wiimote = None
POINTS_TO_BE_TRACKED = 2

tracker = Tracker(POINTS_TO_BE_TRACKED)

def get_wiimote():
    global wiimote
    print("Looking for Wiimote \n Put it in discoverable mode (sync button) then press 1+2 ...")
    wiimote = cwiid.Wiimote()



def loop():
    global wiimote

    def callback(mesg_list, time):
      for mesg in mesg_list:
          if mesg[0] == cwiid.MESG_IR:
              tracker.receive(mesg[1], time)

          elif mesg[0] ==  cwiid.MESG_ERROR:
              print "Error message received"
              global wiimote
              wiimote.close()
              exit(-1)
          else:
              print 'Unknown Report'

    # defaults
    rumble=0
    rpt_mode=0 ; rpt_mode ^= cwiid.RPT_IR
    led = 0 ; led ^= cwiid.LED3_ON


    wiimote.mesg_callback = callback
    wiimote.rumble = rumble
    wiimote.rpt_mode = rpt_mode
    wiimote.led = led
    mesg = True ; wiimote.enable(cwiid.FLAG_MESG_IFC);

    while True:
        pass



def main():
    get_wiimote()

    print("wiimote pegadinho")
    loop()

main()
