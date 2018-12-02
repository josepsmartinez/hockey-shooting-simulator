from __future__ import absolute_import

import os
import sys

import copy
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

    'PUCK_POSITION': cwiid.IR_Y_MAX*0.9,
    'SHOOT_SENSITIVITY': 25,
    'STICK_HEIGHT': 50,

    'CAMERA_ROTATION': 180,

    'WINDOW_SIZE': tuple(map(lambda x: int(x*1.75), (800, 600))),
    'FONT_SCALE': 3.5

}

class hssGUI():
    def __init__(self, cfg):
        self.state = 'init'
        self.cfg = cfg
        self.set_tracker()

        self.IR_texture = create_empty_texture(100, 100)

        """ imgui stuff """
        pygame.init()
        pygame.display.set_mode(cfg['WINDOW_SIZE'], pygame.DOUBLEBUF | pygame.OPENGL)

        io = imgui.get_io()
        io.fonts.add_font_default()
        io.display_size = cfg['WINDOW_SIZE']

        self.renderer = PygameRenderer()

        """ disk output """
        self.output_file = None


        self.colors = {
            'background_not_ok': (255, 50, 50), # vermeho
            'background_waiting': (100, 255, 255), # amarelo
            'background_shooting': (50, 255, 50), # verde

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
            'waiting_shoot' : "READY, SHOOT!",
            'shooting': "CROSS THE SHOOTING LINE"
        }

    def set_tracker(self):
        self.tracker = Tracker(self.cfg['PUCK_POSITION'],
            puck_proximity=self.cfg['SHOOT_SENSITIVITY'],
            stick_height=self.cfg['STICK_HEIGHT'],
            camera_rotation=self.cfg['CAMERA_ROTATION'])

    def get_color(self, color, to_np_array=False):
        rgb_color = self.colors[color][::-1]
        if to_np_array:
            return np.array(rgb_color).astype(np.uint8)
        else:
            return rgb_color

    def new_output_file(self):
        present = datetime.now()
        self.output_file = open(os.path.join('output', present.strftime("%y%m%d%H%M%s")) + '.test', 'w' )


    def end_play(self):
        self.state = 'play_results'

        if self.output_file is not None:
            delta = datetime.now() - self.tracker.logger.logtimestamp
            self.output_file.write("Ending play after %s\n" % (delta.total_seconds()))
            self.output_file = None

    def clear(self):
        glClearColor(0.1, 0.1, 0.1, 0.0)
        glClear(GL_COLOR_BUFFER_BIT)

    """ SCREENS """
    def shooting_subscreen(self, extra_resize=1.0):
        ''' IR data background '''
        img = np.zeros((cwiid.IR_Y_MAX, cwiid.IR_X_MAX, 3), np.uint8)

        ''' different background if calibrated '''
        img += self.get_color({
            'U': 'background_not_ok',
            'W': 'background_waiting',
            'S': 'background_shooting'
        }[self.tracker.state], to_np_array=True)

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
        img = cv2.resize(img, (0,0), fx=extra_resize*1.5, fy=extra_resize*1.5)
        self.IR_texture = cv_image2texture(img, texture=self.IR_texture[0])
        imgui.image(self.IR_texture[0], self.IR_texture[1], self.IR_texture[2])

        ''' message / tip '''
        if self.tracker.state in ('U'):
            imgui.text(self.messages['calibration_not_ok'])
        elif self.tracker.state in ('W'):
            imgui.text(self.messages['waiting_shoot'])
        elif self.tracker.state in ('S'):
            imgui.text(self.messages['shooting'])

    def end_play_subscreen(self):
        ''' Button / action for interrupting a play '''
        if imgui.button("Stop",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/6):
            self.end_play()

    def play_results_screen(self):
        imgui.text("You performed %d shots!" % (self.tracker.shoot_counter))

        if imgui.button("Back to main",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/4):
            self.state = 'main'

    def connection_screen(self):
        imgui.text("---- CONNECTION INSTRUCTIONS ----")

        self.state = 'connecting'

    def main_screen(self):
        #self.tracker.reset_shoot_counter()
        self.set_tracker()

        global wiimote

        if wiimote is None:
            imgui.text("No wiimote detected")

            if imgui.button("Connect",
                width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/4):
                self.state = 'connection'
        else:
            if imgui.button("Free Shooting",
                width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/5):
                self.state = 'free_shoot'

                self.new_output_file()
                self.tracker.set_logging_point(self.output_file)
                self.output_file.write("Starting free shoot \n")

            if imgui.button("Shoot 10",
                width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/5):
                self.state = 'shoot_ten'

            self.new_output_file()
            self.tracker.set_logging_point(self.output_file)
            self.output_file.write("Starting shoot 10 \n")

        if imgui.button("Configuration",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/6):
            self.state = 'edit'

            self.stashed_config = copy.deepcopy(self.cfg)

        if imgui.button("Quit",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/5):
            exit()

    def free_shoot_screen(self):
        io = imgui.get_io()

        self.shooting_subscreen()

        imgui.text("Shoots: %d" % (self.tracker.shoot_counter))

        self.end_play_subscreen()

    def shoot_10_screen(self):
        self.shooting_subscreen()

        imgui.text("Shoots: %d/%d" % (self.tracker.shoot_counter, 10))

        self.end_play_subscreen()

        if self.tracker.shoot_counter >= 10:
            self.end_play()

    def edit_screen(self):
        global wiimote

        imgui.text("%s" % datetime.utcnow())
        imgui.text("Current configuration")

        if imgui.begin_menu("Camera rotation (%s)" % (self.cfg['CAMERA_ROTATION']), True):
            c, _ = imgui.menu_item('0')
            if c:
                self.cfg['CAMERA_ROTATION'] = 0
                self.set_tracker()

            c, _ = imgui.menu_item('180')
            if c:
                self.cfg['CAMERA_ROTATION'] = 180
                self.set_tracker()

            imgui.end_menu()

        c, v = imgui.slider_float('Shoot sensitivity',
            self.cfg['SHOOT_SENSITIVITY'], 5.0, 250.0, '%.1f')
        if c:
            self.cfg['SHOOT_SENSITIVITY'] = v
            self.set_tracker()

        c, v = imgui.slider_float('Stick head length',
            self.cfg['STICK_HEIGHT'], 10.0, 100.0, '%.1f')
        if c:
            self.cfg['STICK_HEIGHT'] = v
            self.set_tracker()

        c, v = imgui.slider_float('Puck height',
            self.cfg['PUCK_POSITION']/float(cwiid.IR_Y_MAX), 0.6, 1.0, '%.2f')
        if c:
            self.cfg['PUCK_POSITION'] = v * cwiid.IR_Y_MAX
            self.set_tracker()

        if wiimote is not None:
            self.shooting_subscreen(extra_resize=0.75)
        else:
            if imgui.button("Connect wiimote",
                width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/10):
                self.state = 'connection'

        if imgui.button("Confirm configuration",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/10):
            self.stashed_config = None
            self.state = 'main'

        if imgui.button("Undo changes",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/10):
            if self.stashed_config is not None:
                self.cfg = copy.deepcopy(self.stashed_config)

        if imgui.button("Discard changes",
            width=self.cfg['WINDOW_SIZE'][0], height=self.cfg['WINDOW_SIZE'][1]/10):
            if self.stashed_config is not None:
                self.cfg = copy.deepcopy(self.stashed_config)

            self.state = 'main'

    """ INTERFACE """
    def main_loop(self):
        global wiimote

        io = imgui.get_io()
        imgui.get_io().font_global_scale = self.cfg['FONT_SCALE']

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
            #'connecting': lambda: self.connection_screen(),
            'init': lambda: self.main_screen(),
            'connection': lambda: self.connection_screen(),
            'main': lambda: self.main_screen(),
            'edit': lambda: self.edit_screen(),
            'play_results': lambda: self.play_results_screen(),
            'free_shoot': lambda: self.free_shoot_screen(),
            'shoot_ten': lambda: self.shoot_10_screen()
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

            self.state = 'main'

def main():
    gui = hssGUI(__CONFIG)

    while 1:
        try:
            gui.main_loop()
        except KeyError as e:
            print(e)


if __name__ == '__main__':
    main()
