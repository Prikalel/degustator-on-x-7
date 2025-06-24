import pygame
from pygame.locals import *
from colors import WHITE, BLACK, GRAY, LIGHT_GREEN, DARK_PURPLE, LIGHT_PURPLE, YELLOW
from window import WIDTH, HEIGHT

class GameUI:
    FONT = pygame.font.SysFont('Raleway', 24)

    def draw_game_ui(self, screen, game_state):
        try:
            background = pygame.image.load('in-game-background.png')
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            screen.blit(background, (0, 0))
        except pygame.error as e:
            print(f"Could not load image: {e}")
            screen.fill(WHITE)

        if game_state.get('current_item'):
            item_name = game_state['current_item'].get('name', 'Unknown Item')
            item_text = FONT.render(item_name, True, BLACK)
            screen.blit(item_text, (WIDTH//2 - item_text.get_width()//2, 100))

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
        progress_width = (starvation / max_starvation) * 200
        pygame.draw.rect(screen, BLACK, (50, 300, 200, 20), 2)
        pygame.draw.rect(screen, LIGHT_GREEN, (50, 300, progress_width, 20))

        money = game_state.get('money', 0)
        money_text = self.FONT.render(f"Баланс: ${money}", True, YELLOW)
        screen.blit(money_text, (400, 50))

        shop_button = pygame.Rect(650, 50, 100, 30)
        pygame.draw.rect(screen, LIGHT_PURPLE, shop_button)
        shop_text = self.FONT.render("Магаз", True, BLACK)
        screen.blit(shop_text, shop_text.get_rect(center=shop_button.center))

        eat_button = pygame.Rect(300, 400, 100, 50)
        skip_button = pygame.Rect(450, 400, 100, 50)
        pygame.draw.rect(screen, GRAY, eat_button)
        pygame.draw.rect(screen, GRAY, skip_button)
        eat_text = self.FONT.render("Съесть", True, BLACK)
        skip_text = self.FONT.render("Пропустить", True, BLACK)
        screen.blit(eat_text, eat_text.get_rect(center=eat_button.center))
        screen.blit(skip_text, skip_text.get_rect(center=skip_button.center))