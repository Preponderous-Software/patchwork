import pygame

#  @author Daniel McCoy Stephenson
#  @since October 2nd, 2025
class RenderWindow:
    """
    RenderWindow class encapsulates Pygame window initialization and management.
    Designed for composition, not inheritance - use as a container for rendering.
    
    Manages:
    - Pygame initialization
    - Window creation and display surface
    - Event loop processing
    - Frame rate control
    - Custom event handlers
    - Teardown, either explicitly via close() or via the context-manager protocol
    """
    
    def __init__(self, title, width, height, resizable=False):
        """
        Initialize the RenderWindow with the specified title and dimensions.

        Args:
            title (str): Window title
            width (int): Initial window width in pixels
            height (int): Initial window height in pixels
            resizable (bool): Whether the user may resize the window. Pygame resizes the
                display surface in place, so the surface returned by get_surface() stays
                valid and its get_size() reports the current dimensions.
        """
        pygame.init()
        if resizable:
            self._surface = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        else:
            self._surface = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)
        self._clock = pygame.time.Clock()
        self._running = True
        self._event_handlers = []

    def __enter__(self):
        """
        Enter the context-manager protocol.

        Returns:
            RenderWindow: This window, so that it can be bound by a with-statement
        """
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """
        Leave the context-manager protocol, tearing the window down.
        Exceptions are not suppressed.
        """
        self.close()
        return False

    def get_surface(self):
        """
        Get the display surface for rendering.
        
        Returns:
            pygame.Surface: The display surface
        """
        return self._surface
    
    def tick(self, fps):
        """
        Control the frame rate by limiting the number of frames per second.
        
        Args:
            fps (int): Target frames per second
        """
        self._clock.tick(fps)
    
    def should_continue(self):
        """
        Process events and check if the window should continue running.
        Handles QUIT events internally and calls registered event handlers.
        
        Returns:
            bool: True if the window should continue running, False otherwise
        """
        if not self._running:
            return False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return False
            # Call all registered event handlers
            for handler in self._event_handlers:
                handler(event)
        
        return self._running
    
    def register_event_handler(self, handler):
        """
        Register a custom event handler function.
        The handler will be called for each event (except QUIT which is handled internally).
        
        Args:
            handler (callable): A function that takes a pygame.Event as parameter
        """
        self._event_handlers.append(handler)

    def close(self):
        """
        Tear the window down, shutting Pygame back down and marking the window as
        no longer running so that should_continue() reports False.
        Calling this more than once is harmless.
        """
        self._running = False
        pygame.quit()
