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
        self.eat_button = pygame.Rect(300, 400, 100, 50)
        self.eat_button_text = "Съесть"

    def handle_event(self, event):
        pass

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
            item_text = self.FONT.render(item_name, True, BLACK)
            screen.blit(item_text, (WIDTH // 2 - item_text.get_width() // 2, 70))
            self.eat_button_text = f"Съесть (+{self.current_item['cost']}$)"
        else:
            self.eat_button_text = "Съесть"

        if game_state.get('current_item'):
            item_name = game_state['current_item'].get('name', 'Unknown Item')
            item_text = self.FONT.render(item_name, True, BLACK)
            screen.blit(item_text, (WIDTH // 2 - item_text.get_width() // 2, 100))
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

        shop_button = pygame.Rect(650, 10, 100, 30)
        pygame.draw.rect(screen, LIGHT_PURPLE, shop_button)
        shop_text = self.FONT.render("Магаз", True, YELLOW)
        screen.blit(shop_text, shop_text.get_rect(center=shop_button.center))

        # Draw and update eat button
        pygame.draw.rect(screen, GRAY, self.eat_button)
        eat_text_surf = self.FONT.render(self.eat_button_text, True, BLACK)
        screen.blit(eat_text_surf, eat_text_surf.get_rect(center=self.eat_button.center))

        skip_button = pygame.Rect(450, 400, 100, 50)
        pygame.draw.rect(screen, GRAY, skip_button)
        skip_text = self.FONT.render("Пропустить", True, BLACK)
        screen.blit(skip_text, skip_text.get_rect(center=skip_button.center))