from __future__ import absolute_import

import sys
from datetime import datetime

import pygame
from OpenGL.GLUT import *
from OpenGL.GL import *
from OpenGL.GLU import *
from imgui.integrations.pygame import PygameRenderer
import imgui
from imgui_datascience import imgui_cv

import cv2
import numpy as np

from capture import get_wiimote, high_callback
wiimote = None

from tracker import Tracker

__CONFIG = {
    'WINDOW_SIZE': (800, 600),

    'LEDS_ON_STICK': 4,
    'PUCK_POSITION': (0, 0)
}

GUI_STATE = 'init'

def no_controller_screen():
    global GUI_STATE

    imgui.text("No wiimote detected")

    if imgui.button("Connect"):
        GUI_STATE = 'connection'

def connection_screen(tracker):
    global wiimote
    global GUI_STATE

    imgui.text("---- CONNECTION INSTRUCTIONS ----")

    GUI_STATE = 'connecting'


def main_screen(tracker):
    global wiimote
    global GUI_STATE

    imgui.text("---- IR DATA (at least) ----")
    imgui.text("[%s] -> %s" % (tracker.state, tracker.current_sources))
    imgui.text("%s" % datetime.utcnow())


    img = np.zeros((1024, 1024), np.uint8)
    img += 255

    for source in tracker.current_sources:
        img = cv2.circle(img, source['pos'], 10*source['size'], (0.5,0.5,0.5), -1)

    imgui_cv.image(img, height=150, title="Detected IR sources")


def clear_screen():
    glClearColor(0.0, 0.0, 0.0, 0.0)
    glClear(GL_COLOR_BUFFER_BIT)
    #glEnd()

def main_loop(tracker, renderer):
    global wiimote
    global GUI_STATE

    io = imgui.get_io()


    for event in pygame.event.get():
        """ these events could turn this loop function into an 'infinite' iterator
        => would get rid of <renderer> arg passing and while <tautology> """
        if event.type == pygame.QUIT:
            sys.exit()

        renderer.process_event(event)


    # start new frame context
    imgui.new_frame()

    # open new window context
    imgui.set_next_window_position(0,0)
    imgui.set_next_window_size(*io.display_size)
    imgui.begin("Main", False,
        flags=imgui.WINDOW_NO_MOVE+imgui.WINDOW_NO_TITLE_BAR)

    # draw screen based on interface state
    {
        'init': lambda: no_controller_screen(),
        'connection': lambda: connection_screen(tracker),
        'active': lambda: main_screen(tracker)

    }[GUI_STATE]()


    # close current window context
    imgui.end()


    # refills background and renders
    clear_screen()

    imgui.render()
    pygame.display.flip()

    # handles wiimote connection after rendering instructions
    if GUI_STATE == 'connecting':
        while wiimote is None:
            wiimote = get_wiimote() # hangs interface
        wiimote.mesg_callback = high_callback(lambda mesg, time: tracker.receive(mesg[1], time))

        GUI_STATE = 'active'

def main():
    cfg = __CONFIG
    tracker = Tracker(cfg['LEDS_ON_STICK'])
    size = cfg['WINDOW_SIZE']

    pygame.init()
    pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL)

    io = imgui.get_io()
    io.fonts.add_font_default()
    io.display_size = size

    renderer = PygameRenderer()

    while 1:
        main_loop(tracker, renderer)

if __name__ == '__main__':
    main()
