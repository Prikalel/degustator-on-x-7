import pygame
import sys

# Initialize Pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 800, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
background = pygame.image.load('main-menu-background.jpg')
background = pygame.transform.scale(background, (WIDTH, HEIGHT))
pygame.display.set_caption("Digustator - Main Menu")

# Colors
WHITE = (255, 255, 255)
LIGHT_PURPLE = (153, 50, 204)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
LIGHT_GREEN = (0, 255, 0)
DARK_PURPLE = (102, 0, 153)

# Fonts
FOOTER_FONT = pygame.font.SysFont('Raleway', 24, bold=True)
FONT = pygame.font.Font(None, 36)
TITLE_FONT = pygame.font.Font(None, 64)

# Button class
class Button:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = GRAY

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_surf = FONT.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

# Create buttons
play_button = Button(300, 200, 200, 50, "Играть")
tutor_button = Button(300, 300, 200, 50, "Туториал")

# Footer text
footer_text = "Добро пожаловать на Планету X-7!\nвы - дегустатор, исследователь новой еды для человеческой расы. @velikiy_prikalel"

def show_tutorial():
    try:
        TUTORIAL_FOND = pygame.font.Font(None, 24)
        TUTORIAL_FOND_BOLD = pygame.font.SysFont(None, 24, bold=True)
        with open('tutorial.txt', 'r', encoding='utf-8') as file:
            content = file.read()
        tutorial_lines = content.split('\n')
        SCREEN.fill(WHITE)
        for i, line in enumerate(tutorial_lines):
            text = (TUTORIAL_FOND_BOLD if line.startswith("##") else TUTORIAL_FOND).render(line, True, BLACK)
            SCREEN.blit(text, (10, 10 + i * 30))
        back_text = TUTORIAL_FOND.render("Нажмите ESC для возврата в меню", True, LIGHT_GREEN)
        SCREEN.blit(back_text, (50, 550))
        pygame.display.flip()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
    except FileNotFoundError:
        print("Tutorial file not found!")

def main_menu():
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if play_button.is_clicked(event):
                print("Starting game...")
                # Game start logic will be added here later
            if tutor_button.is_clicked(event):
                show_tutorial()

        # Draw background
        SCREEN.blit(background, (0, 0))

        # Draw title
        # Draw even thicker shadow text (three layers)
        # Outer layer (furtherst from text)
        shadow_text_outer = TITLE_FONT.render("ДЕГУСТАТОР", True, BLACK)
        shadow_rect_outer = shadow_text_outer.get_rect(center=(WIDTH//2 + 6, 100 + 6))
        SCREEN.blit(shadow_text_outer, shadow_rect_outer)
        
        # Middle layer (closer to text)
        shadow_text_middle = TITLE_FONT.render("ДЕГУСТАТОР", True, BLACK)
        shadow_rect_middle = shadow_text_middle.get_rect(center=(WIDTH//2 + 4, 100 + 4))
        SCREEN.blit(shadow_text_middle, shadow_rect_middle)
        
        # Inner layer (closest to text)
        shadow_text_inner = TITLE_FONT.render("ДЕГУСТАТОР", True, BLACK)
        shadow_rect_inner = shadow_text_inner.get_rect(center=(WIDTH//2 + 2, 100 + 2))
        SCREEN.blit(shadow_text_inner, shadow_rect_inner)
        
        # Draw main text
        title_text = TITLE_FONT.render("ДЕГУСТАТОР", True, LIGHT_PURPLE)
        title_rect = title_text.get_rect(center=(WIDTH//2, 100))
        SCREEN.blit(title_text, title_rect)

        # Draw buttons
        play_button.draw(SCREEN)
        tutor_button.draw(SCREEN)

        # Draw footer
        # Draw even thicker shadow for footer (three layers)
        footer_lines = footer_text.split('\n')
        y_pos = HEIGHT - 40 + 4  # Start position for outer shadow
        
        for line in footer_lines:
            # Outer layer (furtherst from text)
            footer_shadow_outer = FOOTER_FONT.render(line, True, BLACK)
            footer_shadow_rect_outer = footer_shadow_outer.get_rect(center=(WIDTH//2 + 6, y_pos))
            SCREEN.blit(footer_shadow_outer, footer_shadow_rect_outer)
            
            # Middle layer (closer to text)
            footer_shadow_middle = FOOTER_FONT.render(line, True, BLACK)
            footer_shadow_rect_middle = footer_shadow_middle.get_rect(center=(WIDTH//2 + 4, y_pos - 2))
            SCREEN.blit(footer_shadow_middle, footer_shadow_rect_middle)
            
            # Inner layer (closest to text)
            footer_shadow_inner = FOOTER_FONT.render(line, True, BLACK)
            footer_shadow_rect_inner = footer_shadow_inner.get_rect(center=(WIDTH//2 + 2, y_pos - 4))
            SCREEN.blit(footer_shadow_inner, footer_shadow_rect_inner)
            
            y_pos += 30
        
        # Draw main footer text
        footer_lines = footer_text.split('\n')
        y_pos = HEIGHT - 40
        for line in footer_lines:
            footer_surf = FOOTER_FONT.render(line, True, LIGHT_GREEN)
            footer_rect = footer_surf.get_rect(center=(WIDTH//2, y_pos))
            SCREEN.blit(footer_surf, footer_rect)
            y_pos += 30

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main_menu()