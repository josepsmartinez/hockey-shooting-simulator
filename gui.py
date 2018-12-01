from __future__ import absolute_import

import sys
from datetime import datetime

import pygame
import OpenGL.GL as gl
from OpenGL.GL import *
from imgui.integrations.pygame import PygameRenderer
import imgui

import cv2
import numpy as np

import cwiid

from interface_utils import cv_image2texture, create_empty_texture
from capture import get_wiimote, high_callback
wiimote = None

from tracker import Tracker

__CONFIG = {
    'LEDS_ON_STICK': 2,
    'TRIGGER_LED': 0,

    'PUCK_POSITION': tuple(map(int, (cwiid.IR_X_MAX*0.5, cwiid.IR_Y_MAX*0.9))),
    'SHOOT_SENSITIVITY': 25,

    'CAMERA_ROTATION': 180,

    'WINDOW_SIZE': tuple(map(lambda x: int(x*1.75), (800, 600))),
}

class hssGUI():
    def __init__(self, cfg):
        self.state = 'init'
        self.cfg = cfg
        self.tracker = Tracker(cfg['LEDS_ON_STICK'], cfg['TRIGGER_LED'],
            cfg['PUCK_POSITION'], puck_proximity=cfg['SHOOT_SENSITIVITY'],
            camera_rotation=cfg['CAMERA_ROTATION'])

        self.IR_texture = create_empty_texture(100, 100)

        """ imgui stuff """
        pygame.init()
        pygame.display.set_mode(cfg['WINDOW_SIZE'], pygame.DOUBLEBUF | pygame.OPENGL)

        io = imgui.get_io()
        io.fonts.add_font_default()
        io.display_size = cfg['WINDOW_SIZE']

        self.renderer = PygameRenderer()

        """ disk output """
        self.output_file = open('output/test.out', 'w')


        self.colors = {
            'background_not_ok': (255, 50, 50), # vermeho
            'background_waiting': (100, 255, 100), # amarelo
            'background_shooting': (50, 50, 255), # verde

            'puck': (200, 0, 200), # roxo
            'shooting_line': (250, 50, 50), # vermelho
            'LED_normal': (0, 0, 0), # preto
            'LED_calibracao': (100, 100, 100),
            'LED_virtual': (200, 200, 200),
            'LED_1': (200, 0, 0), # vermelho
            'LED_2': (0 , 0, 200), # azul
        }

        self.messages = {
            'calibration_not_ok' : "UNCALIBRATED STICK! PRESS THE BUTTON!",
            'calibration_ok' : "READY, SHOOT!",
        }

    def get_color(self, color, to_np_array=False):
        rgb_color = self.colors[color][::-1]
        if to_np_array:
            return np.array(rgb_color).astype(np.uint8)
        else:
            return rgb_color

    def clear(self):
        glClearColor(0.1, 0.1, 0.1, 0.0)
        glClear(GL_COLOR_BUFFER_BIT)

    """ SCREENS """
    def no_controller_screen(self):
        imgui.text("No wiimote detected")

        if imgui.button("Connect"):
            self.state = 'connection'

    def connection_screen(self):
        imgui.text("---- CONNECTION INSTRUCTIONS ----")

        self.state = 'connecting'

    def main_screen(self):
        if imgui.button("Free Shooting"):
            self.state = 'free_shoot'

    def free_shoot_screen(self):
        io = imgui.get_io()

        ''' IR data background '''
        img = np.zeros((cwiid.IR_Y_MAX, cwiid.IR_X_MAX, 3), np.uint8)


        ''' different background if calibrated '''
        img += self.get_color({
            'U': 'background_not_ok',
            'W': 'background_waiting',
            'S': 'background_shooting'
        }[self.tracker.state], to_np_array=True)
        """        if self.tracker.state not in ('U'):
            #img += np.array((150, 255, 150)).astype(np.uint8)
            img += self.get_color('background_waiting', to_np_array=True)
        else:
            #img += np.array((100, 100, 255)).astype(np.uint8)
            img += self.get_color('background_not_ok', to_np_array=True)
        """
        ''' draw detected sources '''
        for source in self.tracker.current_sources:
            img = cv2.circle(img, source['pos'], 10, self.get_color('LED_normal'), -1)

        ''' draws touching point '''
        if self.tracker.touching_point is not None:
            img = cv2.circle(img, self.tracker.touching_point, self.tracker.puck_proximity, self.get_color('LED_virtual'), -1)

        ''' draws shooting line '''
        if self.tracker.state in ('W', 'S'):
            img = cv2.line(img, (0, int(self.tracker.shooting_line)), (cwiid.IR_X_MAX, int(self.tracker.shooting_line)), self.get_color('shooting_line'))

        ''' draws tracking result (debugging) '''
        if self.tracker.current_snapshot is not None:
            img = cv2.circle(img, self.tracker.current_snapshot[0]['pos'], 10, self.get_color('LED_1'), -1)
            img = cv2.circle(img, self.tracker.current_snapshot[1]['pos'], 10, self.get_color('LED_2'), -1)

        ''' draw puck position '''
        if self.tracker.state not in ('S'):
            img = cv2.circle(img, self.tracker.puck_position, 10, self.get_color('puck'), -1)



        ''' updates texture '''
        img = cv2.resize(img, (0,0), fx=1.5, fy=1.5)
        self.IR_texture = cv_image2texture(img, texture=self.IR_texture[0])
        imgui.image(self.IR_texture[0], self.IR_texture[1], self.IR_texture[2])

        '''  '''
        imgui.text("---- IR DATA (at least) ----")
        imgui.text("[%s] -> %s" % (self.tracker.state, self.tracker.current_snapshot))
        imgui.text("%s" % datetime.utcnow())
        imgui.text("Camera rotation: %s" % (self.cfg['CAMERA_ROTATION']))


        ''' '''
        if imgui.button("Back to main"):
            self.state = 'main'

        if self.tracker.state in ('W', 'S'):
            self.tracker.disk_state_dump(self.output_file, fix_output=4)


    """ INTERFACE """
    def main_loop(self):
        global wiimote

        io = imgui.get_io()

        self.clear()


        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                glEnd()
                sys.exit()

            self.renderer.process_event(event)

        ''' start new frame context '''
        imgui.new_frame()

        ''' open new window context '''
        imgui.set_next_window_position(0,0)
        imgui.set_next_window_size(*io.display_size)
        imgui.begin("Main", False,
            flags=imgui.WINDOW_NO_MOVE+imgui.WINDOW_NO_TITLE_BAR)

        ''' draw screen based on interface state '''
        {
            'init': lambda: self.no_controller_screen(),
            'connection': lambda: self.connection_screen(),
            'main': lambda: self.main_screen(),
            'free_shoot': lambda: self.free_shoot_screen()
        }[self.state]()


        ''' close current window context '''
        imgui.end()


        ''' refills background and renders '''
        self.clear()

        imgui.render()
        pygame.display.flip()

        ''' handles wiimote connection after rendering instructions '''
        if self.state == 'connecting':
            while wiimote is None:
                wiimote = get_wiimote() # hangs interface
            wiimote.mesg_callback = high_callback(lambda mesg, time: self.tracker.receive(mesg[1], time))

            #self.state = 'main'
            self.state = 'free_shoot'

def main():
    gui = hssGUI(__CONFIG)

    while 1:
        gui.main_loop()

if __name__ == '__main__':
    main()
