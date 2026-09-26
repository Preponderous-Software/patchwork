import unittest
from unittest.mock import MagicMock, patch


class TestRenderWindow(unittest.TestCase):
    def setUp(self):
        self.pygame_patcher = patch("render_window.pygame")
        self.mock_pygame = self.pygame_patcher.start()
        self.mock_pygame.QUIT = "QUIT_SENTINEL"
        self.addCleanup(self.pygame_patcher.stop)

        from render_window import RenderWindow
        self.RenderWindow = RenderWindow

    def test_init_sets_up_pygame_window(self):
        window = self.RenderWindow("Title", 640, 480)

        self.mock_pygame.init.assert_called_once()
        self.mock_pygame.display.set_mode.assert_called_once_with((640, 480))
        self.mock_pygame.display.set_caption.assert_called_once_with("Title")
        self.assertIs(window.get_surface(), self.mock_pygame.display.set_mode.return_value)

    def test_resizable_window_is_created_with_the_resizable_flag(self):
        self.mock_pygame.RESIZABLE = "RESIZABLE_SENTINEL"

        window = self.RenderWindow("Title", 640, 480, resizable=True)

        self.mock_pygame.display.set_mode.assert_called_once_with((640, 480), "RESIZABLE_SENTINEL")
        self.assertIs(window.get_surface(), self.mock_pygame.display.set_mode.return_value)

    def test_tick_delegates_to_clock(self):
        window = self.RenderWindow("Title", 640, 480)

        window.tick(30)

        self.mock_pygame.time.Clock.return_value.tick.assert_called_once_with(30)

    def test_should_continue_true_and_dispatches_non_quit_events(self):
        window = self.RenderWindow("Title", 640, 480)
        event = MagicMock(type="KEYDOWN_SENTINEL")
        self.mock_pygame.event.get.return_value = [event]
        handler = MagicMock()
        window.register_event_handler(handler)

        result = window.should_continue()

        self.assertTrue(result)
        handler.assert_called_once_with(event)

    def test_should_continue_false_after_quit_event(self):
        window = self.RenderWindow("Title", 640, 480)
        quit_event = MagicMock(type="QUIT_SENTINEL")
        self.mock_pygame.event.get.return_value = [quit_event]

        result = window.should_continue()

        self.assertFalse(result)

    def test_handlers_not_dispatched_for_quit_event(self):
        window = self.RenderWindow("Title", 640, 480)
        quit_event = MagicMock(type="QUIT_SENTINEL")
        self.mock_pygame.event.get.return_value = [quit_event]
        handler = MagicMock()
        window.register_event_handler(handler)

        window.should_continue()

        handler.assert_not_called()

    def test_close_quits_pygame(self):
        window = self.RenderWindow("Title", 640, 480)

        window.close()

        self.mock_pygame.quit.assert_called_once()

    def test_should_continue_false_after_close_without_polling_events(self):
        window = self.RenderWindow("Title", 640, 480)
        window.close()

        result = window.should_continue()

        self.assertFalse(result)
        self.mock_pygame.event.get.assert_not_called()

    def test_context_manager_yields_window_and_closes_on_exit(self):
        with self.RenderWindow("Title", 640, 480) as window:
            self.assertIsInstance(window, self.RenderWindow)
            self.mock_pygame.quit.assert_not_called()

        self.mock_pygame.quit.assert_called_once()

    def test_context_manager_closes_and_propagates_exception(self):
        with self.assertRaises(ValueError):
            with self.RenderWindow("Title", 640, 480):
                raise ValueError("boom")

        self.mock_pygame.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
