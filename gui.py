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
    'WINDOW_SIZE': tuple(map(lambda x: int(x*1.5), (800, 600))),

    'CAMERA_ROTATION': 180,
    'LEDS_ON_STICK': 4,
    'PUCK_POSITION': tuple(map(int, (cwiid.IR_X_MAX*0.5, cwiid.IR_Y_MAX*0.9)))
}

class hssGUI():
    def __init__(self, cfg):
        self.state = 'init'
        self.cfg = cfg
        self.tracker = Tracker(cfg['LEDS_ON_STICK'], cfg['PUCK_POSITION'],
            camera_rotation=cfg['CAMERA_ROTATION'])

        self.IR_texture = create_empty_texture(100, 100)

        # imgui stuff
        pygame.init()
        pygame.display.set_mode(cfg['WINDOW_SIZE'], pygame.DOUBLEBUF | pygame.OPENGL)

        io = imgui.get_io()
        io.fonts.add_font_default()
        io.display_size = cfg['WINDOW_SIZE']

        self.renderer = PygameRenderer()

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
        io = imgui.get_io()

        ''' IR data background '''
        img = np.zeros((cwiid.IR_Y_MAX, cwiid.IR_X_MAX, 3), np.uint8)
        img += 255

        ''' draw detected sources '''
        for source in self.tracker.current_sources:
            img = cv2.circle(img, source['pos'], 10*source['size'], (0.5,0.5,0.5), -1)

        ''' draw puck position '''
        img = cv2.circle(img, self.tracker.puck_position, 10, (0,255,255), -1)

        ''' updates texture '''
        self.IR_texture = cv_image2texture(img, texture=self.IR_texture[0])
        imgui.image(self.IR_texture[0], self.IR_texture[1], self.IR_texture[2])

        '''  '''
        imgui.text("---- IR DATA (at least) ----")
        imgui.text("[%s] -> %s" % (self.tracker.state, self.tracker.current_sources))
        imgui.text("%s" % datetime.utcnow())
        imgui.text("Camera rotation: %s" % (self.cfg['CAMERA_ROTATION']))


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
            'active': lambda: self.main_screen()
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

            self.state = 'active'

def main():
    gui = hssGUI(__CONFIG)

    while 1:
        gui.main_loop()

if __name__ == '__main__':
    main()
