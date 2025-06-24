import pygame
from pygame.locals import *
from colors import WHITE, BLACK, GRAY, LIGHT_GREEN, DARK_PURPLE, LIGHT_PURPLE, YELLOW
from window import WIDTH, HEIGHT
import items_provider

class GameUI:
    FONT = pygame.font.SysFont('Raleway', 24)

    def __init__(self):
        self.current_item = None
        self.set_new_item()
        self.eat_button = pygame.Rect(300, 400, 140, 50)
        self.eat_button_text = "Съесть"
        self.skip_button = pygame.Rect(450, 400, 140, 50)
        self.shop_button = pygame.Rect(650, 10, 100, 30)
        self._cached_images = {}

    @staticmethod
    def is_button_clicked(event, rect: pygame.Rect) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(event.pos)

    def handle_event(self, event):
        if GameUI.is_button_clicked(event, self.eat_button):
            print("eat!")
        elif GameUI.is_button_clicked(event, self.skip_button):
            print("skip!")
        elif GameUI.is_button_clicked(event, self.shop_button):
            print("shop!")

    def load_image(self, image_path):
        if image_path not in self._cached_images:
            try:
                image = pygame.image.load(image_path)
                image = pygame.transform.scale(image, (100, 100))
                self._cached_images[image_path] = image
            except pygame.error as e:
                print(f"Error loading image: {e}")
                return
        return self._cached_images[image_path]

    def set_new_item(self):
        self.current_item = items_provider.get_random_item()

    def draw_game_ui(self, screen, game_state):
        try:
            background = pygame.image.load('in-game-background.png')
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            screen.blit(background, (0, 0))
        except pygame.error as e:
            print(f"Could not load image: {e}")
            screen.fill(WHITE)

        if self.current_item:
            item_name = self.current_item.get('name', 'Unknown Item')
            item_text = self.FONT.render(item_name, True, LIGHT_GREEN)
            screen.blit(item_text, (WIDTH // 2 - item_text.get_width() // 2, 70))
            self.eat_button_text = f"Съесть (+{self.current_item['cost']}$)"
            image_path = self.current_item.get('image')
            if image_path:
                try:
                    # Load the image if not already loaded - optional: cache images for efficiency
                    item_image = self.load_image(image_path)
                    # Calculate position to center the image
                    image_rect = item_image.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                    # Blit the image onto the screen
                    screen.blit(item_image, image_rect)
                except pygame.error as e:
                    print(f"Error loading item image '{image_path}': {e}")
        else:
            self.eat_button_text = "Съесть"

        effect_y = 200
        for effect in game_state.get('effects', []):
            effect_name = effect.get('name', 'Unnamed Effect')
            effect_text = self.FONT.render(effect_name, True, BLACK)
            screen.blit(effect_text, (50, effect_y))
            effect_y += 30

        starvation = game_state.get('starvation', 0)
        max_starvation = 3
        if starvation > max_starvation:
            starvation = max_starvation

        starvation_label = self.FONT.render("Голод", True, BLACK)
        screen.blit(starvation_label, (10, 35))

        progress_width = (starvation / max_starvation) * 200
        pygame.draw.rect(screen, BLACK, (10, 10, 200, 20), 2)
        pygame.draw.rect(screen, LIGHT_GREEN, (10, 10, progress_width, 20))

        money = game_state.get('money', 0)
        money_text = self.FONT.render(f"Баланс: ${money}", True, YELLOW)
        screen.blit(money_text, (400, 10))

        pygame.draw.rect(screen, LIGHT_PURPLE, self.shop_button)
        shop_text = self.FONT.render("Магаз", True, YELLOW)
        screen.blit(shop_text, shop_text.get_rect(center=self.shop_button.center))

        # Draw and update eat button
        pygame.draw.rect(screen, GRAY, self.eat_button)
        eat_text_surf = self.FONT.render(self.eat_button_text, True, BLACK)
        screen.blit(eat_text_surf, eat_text_surf.get_rect(center=self.eat_button.center))

        # Draw and update skip button with multiline label
        pygame.draw.rect(screen, GRAY, self.skip_button)
        skip_text_lines = ["Пропустить", "(-1голод)"]
        line_spacing = 4  # space between lines in pixels
        total_height = 0
        rendered_lines = []

        # Render each line
        for line in skip_text_lines:
            surf = self.FONT.render(line, True, BLACK)
            rendered_lines.append(surf)
            total_height += surf.get_height()

        # Starting y position to center the multiline text within the button
        y_offset = self.skip_button.centery - total_height // 2

        for surf in rendered_lines:
            rect = surf.get_rect(center=(self.skip_button.centerx, y_offset + surf.get_height() // 2))
            screen.blit(surf, rect)
            y_offset += surf.get_height() + line_spacing