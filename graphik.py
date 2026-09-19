import pygame

black = (0,0,0)
white = (255,255,255)
red = (200,0,0)
green = (0,200,0)
blue = (0,0,200)

graphiklibversion = "0.2-alpha-1"

#  @author Daniel McCoy Stephenson
#  @since February 3rd, 2022
class Graphik:
    def __init__(self, gameDisplay):
        self.gameDisplay = gameDisplay

        self.version = graphiklibversion

        # whether the mouse button was already down the last time each button was drawn,
        # keyed by the button's rectangle, so that a held click fires its function only once
        self.buttonPressStates = {}

    def getGameDisplay(self):
        return self.gameDisplay

    def getVersion(self):
        return self.version

    def drawRectangle(self, xpos, ypos, width, height, color):
        pygame.draw.rect(self.gameDisplay, color, [xpos, ypos, width, height])

    def drawText(self, text, xpos, ypos, size, color):
        myFont = pygame.font.Font('freesansbold.ttf', size)
        textSurface = myFont.render(text, True, color)
        textRectangle = textSurface.get_rect()
        textRectangle.center = ((xpos, ypos))
        self.gameDisplay.blit(textSurface, textRectangle)

    def drawButton(self, xpos, ypos, width, height, colorBox, colorText, sizeText, text, function):
        self.drawRectangle(xpos, ypos, width, height, colorBox)
        self.drawText(text, xpos + (width//2), ypos + (height//2), sizeText, colorText)

        # if clicked then do function - only on the frame the mouse button goes down over the
        # box, not on every frame it is held there, since this is called once per frame
        buttonKey = (xpos, ypos, width, height)
        wasPressed = self.buttonPressStates.get(buttonKey, False)
        isPressed = pygame.mouse.get_pressed()[0] == 1
        self.buttonPressStates[buttonKey] = isPressed
        if isPressed and not wasPressed:
            mouse = pygame.mouse.get_pos()
            if (xpos + width > mouse[0] > xpos and ypos + height > mouse[1] > ypos):
                function()
