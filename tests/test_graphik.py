import inspect
import unittest
from unittest.mock import MagicMock, patch


class GraphikTestCase(unittest.TestCase):
    def setUp(self):
        self.pygame_patcher = patch("graphik.pygame")
        self.mock_pygame = self.pygame_patcher.start()
        self.addCleanup(self.pygame_patcher.stop)

        import graphik
        self.graphik_module = graphik
        self.Graphik = graphik.Graphik
        self.surface = MagicMock(name="surface")


class TestConstruction(GraphikTestCase):
    """Regression coverage for the shadowed no-argument constructor (#20)."""

    def test_exactly_one_init_is_defined(self):
        source = inspect.getsource(self.Graphik)

        self.assertEqual(source.count("def __init__"), 1)

    def test_construction_with_a_display_keeps_it(self):
        graphik = self.Graphik(self.surface)

        self.assertIs(graphik.getGameDisplay(), self.surface)
        self.assertEqual(graphik.getVersion(), self.graphik_module.graphiklibversion)

    def test_construction_does_not_create_a_display_of_its_own(self):
        self.Graphik(self.surface)

        self.mock_pygame.display.set_mode.assert_not_called()

    def test_construction_without_a_display_is_rejected(self):
        with self.assertRaises(TypeError):
            self.Graphik()


class TestDrawing(GraphikTestCase):
    def test_draw_rectangle_draws_onto_the_display(self):
        graphik = self.Graphik(self.surface)

        graphik.drawRectangle(10, 20, 30, 40, (1, 2, 3))

        self.mock_pygame.draw.rect.assert_called_once_with(self.surface, (1, 2, 3), [10, 20, 30, 40])

    def test_draw_text_centres_the_rendered_text_on_the_position(self):
        graphik = self.Graphik(self.surface)
        text_surface = self.mock_pygame.font.Font.return_value.render.return_value

        graphik.drawText("hello", 100, 200, 16, (1, 2, 3))

        self.mock_pygame.font.Font.assert_called_once_with("freesansbold.ttf", 16)
        self.mock_pygame.font.Font.return_value.render.assert_called_once_with("hello", True, (1, 2, 3))
        self.assertEqual(text_surface.get_rect.return_value.center, (100, 200))
        self.surface.blit.assert_called_once_with(text_surface, text_surface.get_rect.return_value)


class TestDrawButton(GraphikTestCase):
    """Regression coverage for the callback firing on every held frame (#22)."""

    BUTTON = (10, 10, 100, 50)
    INSIDE = (50, 30)
    OUTSIDE = (500, 500)

    def setUp(self):
        super().setUp()
        self.graphik = self.Graphik(self.surface)
        self.function = MagicMock(name="function")

    def drawFrame(self, mouse, pressed, button=BUTTON):
        """Draw the button for one frame with the mouse at the given position and state."""
        self.mock_pygame.mouse.get_pos.return_value = mouse
        self.mock_pygame.mouse.get_pressed.return_value = (1 if pressed else 0, 0, 0)
        self.graphik.drawButton(*button, (1, 1, 1), (2, 2, 2), 12, "Go", self.function)

    def test_button_is_drawn_as_a_box_with_centred_text(self):
        self.drawFrame(self.OUTSIDE, pressed=False)

        self.mock_pygame.draw.rect.assert_called_once_with(self.surface, (1, 1, 1), [10, 10, 100, 50])
        self.mock_pygame.font.Font.return_value.render.assert_called_once_with("Go", True, (2, 2, 2))
        text_rect = self.mock_pygame.font.Font.return_value.render.return_value.get_rect.return_value
        self.assertEqual(text_rect.center, (60, 35))

    def test_a_press_over_the_button_fires_the_function_once(self):
        self.drawFrame(self.INSIDE, pressed=False)
        self.drawFrame(self.INSIDE, pressed=True)

        self.function.assert_called_once_with()

    def test_holding_the_button_down_over_several_frames_fires_only_once(self):
        self.drawFrame(self.INSIDE, pressed=False)
        for _ in range(5):
            self.drawFrame(self.INSIDE, pressed=True)

        self.function.assert_called_once_with()

    def test_releasing_and_pressing_again_fires_a_second_time(self):
        self.drawFrame(self.INSIDE, pressed=True)
        self.drawFrame(self.INSIDE, pressed=False)
        self.drawFrame(self.INSIDE, pressed=True)

        self.assertEqual(self.function.call_count, 2)

    def test_a_press_outside_the_button_does_not_fire(self):
        self.drawFrame(self.OUTSIDE, pressed=True)

        self.function.assert_not_called()

    def test_hovering_without_pressing_does_not_fire(self):
        for _ in range(3):
            self.drawFrame(self.INSIDE, pressed=False)

        self.function.assert_not_called()

    def test_dragging_a_held_press_onto_the_button_does_not_fire(self):
        self.drawFrame(self.OUTSIDE, pressed=True)
        self.drawFrame(self.INSIDE, pressed=True)

        self.function.assert_not_called()

    def test_each_button_tracks_its_own_press_state(self):
        other_button = (200, 10, 100, 50)
        inside_other = (250, 30)

        # a press that goes down over the second button while the first is drawn earlier in
        # the same frame must still reach the second button's function
        self.drawFrame(inside_other, pressed=False)
        self.drawFrame(inside_other, pressed=False, button=other_button)
        self.drawFrame(inside_other, pressed=True)
        self.drawFrame(inside_other, pressed=True, button=other_button)

        self.function.assert_called_once_with()
