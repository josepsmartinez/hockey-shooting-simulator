from __future__ import absolute_import

import sys

import pygame
import OpenGL.GL as gl
from imgui.integrations.pygame import PygameRenderer
import imgui

from capture import get_wiimote, high_callback
wiimote = None

from tracker import Tracker

__CONFIG = {
    'LEDS_ON_STICK': 4,
    'PUCK_POSITION': (0,0)
}

def main_loop(renderer):
    global wiimote
    cfg = __CONFIG
    tracker = Tracker(cfg['LEDS_ON_STICK'])

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

    # draw text label inside of current window
    if wiimote is None:
        imgui.text("Nao tem wii!!")

        if imgui.button("Pegar wii"):
            while wiimote is None:
                wiimote = get_wiimote()

            wiimote.mesg_callback = high_callback(lambda mesg, time: tracker.receive(mesg[1], time))
    else:
        imgui.text("Achei um wii!!")




    # close current window context
    imgui.end()

    # refills background and renders
    background_color = (0,0,1)
    gl.glClearColor(*(background_color + tuple([1])))
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    imgui.render()

    pygame.display.flip()

def main():
    pygame.init()

    size = 800, 600

    pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL)

    io = imgui.get_io()
    io.fonts.add_font_default()
    io.display_size = size

    renderer = PygameRenderer()

    while 1:
        main_loop(renderer)

if __name__ == '__main__':
    main()
