import pygame
import numpy as np
import cv2
import OpenGL.GL as gl
from OpenGL.GL import *


def cv_image2texture(cv_image_bgr, texture = None):
    image_rgb = cv2.cvtColor(cv_image_bgr, cv2.COLOR_BGR2RGB)
    image_rgb = cv2.resize(image_rgb, None, fx=0.5, fy=0.5)
    image_rgb = cv2.flip(image_rgb, -1)
    pygame_img = pygame.image.frombuffer(image_rgb.tostring(), image_rgb.shape[1::-1], "RGB")
    pygame_img = pygame.transform.flip(pygame_img, True, True)

    textureSurface = pygame.transform.flip(pygame_img, False, True)

    textureData = pygame.image.tostring(textureSurface, "RGBA", 1)

    width = textureSurface.get_width()
    height = textureSurface.get_height()

    if texture is None:
        texture = gl.glGenTextures(1)

    glBindTexture(GL_TEXTURE_2D, texture)

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, textureData)

    return texture, width, height


def create_empty_texture(width, height):
    size = height, width, 3
    m = np.zeros(size, dtype=np.uint8)

    return cv_image2texture(m)
