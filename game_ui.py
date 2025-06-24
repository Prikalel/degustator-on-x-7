import tkinter as tk
from tkinter import messagebox
import pygame
from pygame.locals import *
from colors import WHITE, BLACK, GRAY, LIGHT_GREEN, DARK_PURPLE, LIGHT_PURPLE, YELLOW
from window import WIDTH, HEIGHT
import items_provider
import effect_provider
from effect_provider import Effect
import threading
import time
from PIL import Image
import random
from shop import ImageListDialog

max_starvation = 3

class GameUI:
    FONT = pygame.font.SysFont('Raleway', 24)

    def __init__(self):
        self.current_item = None
        self.is_loading = False
        self.is_in_shop = False
        self.loading_frames = self.load_loading_animation()
        self.current_loading_frame = 0
        self.loading_animation_timer = 0
        self._cached_mappings = []
        self.set_new_item()
        self.eat_button = pygame.Rect(300, 400, 140, 50)
        self.eat_button_text = "Съесть"
        self.skip_button = pygame.Rect(450, 400, 140, 50)
        self.shop_button = pygame.Rect(650, 10, 100, 30)
        self._cached_images = {}

    def load_loading_animation(self):
        try:
            # Load the loading animation frames - adjust as needed based on your gif structure
            # This is a simplified approach; you might need to use a library like PIL for actual gif parsing
            im = Image.open("loading.gif")
            frames = []
            try:
                while 1:
                    im.seek(im.tell()+1)
                    # add "im" to frames
                    bytess = im.tobytes()
                    frames.append(pygame.transform.scale(pygame.image.frombytes(bytess, (512, 512), "RGBA"), (100, 100)))
            except EOFError:
                pass
            return frames
        except pygame.error as e:
            print(f"Error loading loading animation: {e}")
            # Create a fallback loading indicator
            surf = pygame.Surface((100, 100), pygame.SRCALPHA)
            pygame.draw.circle(surf, LIGHT_PURPLE, (50, 50), 40)
            return [surf]

    @staticmethod
    def is_button_clicked(event, rect: pygame.Rect) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(event.pos)

    def handle_event(self, event, game_state):
        # Ignore button clicks when loading
        if self.is_loading or self.is_in_shop:
            return
            
        if GameUI.is_button_clicked(event, self.eat_button):
            self.eat(game_state, self.current_item, True)
        elif GameUI.is_button_clicked(event, self.skip_button):
            starvation = game_state.get('starvation', 0)
            if starvation > 0:
                # Decrease starvation by 1
                game_state['starvation'] = starvation - 1
                # Get next item
                self.set_new_item()
                print("skip!")
            else:
                # Game over - starvation is 0
                self._show_game_over(game_state)
                return
            game_state['rounds_count'] = game_state['rounds_count'] + 1
        elif GameUI.is_button_clicked(event, self.shop_button):
            print("shop!")
            self.is_in_shop = True
            if len(self._cached_mappings) == 0:
                root = tk.Tk()
                root.withdraw()  # Hide the main window
                messagebox.showinfo("Магазин", "В магазине пусто. Сделайте хотя бы 1 выбор!")
                root.destroy()
            else:
                root = tk.Tk()
                app = ImageListDialog(root, self._cached_mappings)
                root.mainloop()
                if app.bouth_item:
                    if app.bouth_item["item"]["cost"]*2 > game_state["money"]:
                        root = tk.Tk()
                        root.withdraw()  # Hide the main window
                        messagebox.showinfo("Мало денег", "Вы не можете купить " + app.bouth_item["item"]["name"] + ' потому что он стоит ' + str(app.bouth_item["item"]["cost"]*2) + " а у вас всего " + str(game_state["money"]))
                        root.destroy()
                    else:
                        game_state["money"] = game_state["money"] - app.bouth_item["item"]["cost"]*2
                        self.eat(game_state, app.bouth_item["item"], False)
                        if "count_bouth" in app.bouth_item["item"]:
                            app.bouth_item["item"]["count_bouth"] = app.bouth_item["item"]["count_bouth"] + 1
                        else:
                            app.bouth_item["item"]["count_bouth"] = 1
                        if (app.bouth_item["item"]["count_bouth"]>=3):
                            self._cached_mappings = [i for i in self._cached_mappings if i["item"] != app.bouth_item["item"]]
            self.is_in_shop = False
            print("done shoping ")

    def eat(self, game_state, item, increment_cost: bool):
        print("eat! starvation: " + str(game_state['starvation']))
        
        # Check if current item is in cached mappings to use the same effect
        effect = None
        for mapping in self._cached_mappings:
            if mapping['item'] == item:
                effect = mapping['effect']
                print("Using cached effect for repeated item")
                break
        
        # If not found in cache, get a new random effect
        if effect is None:
            effect = effect_provider.get_random_effect()
            
            # Save item and effect mapping for future reference
            if item:
                print("Added item " + item["name"])
                self._cached_mappings.append({
                    'item': item,
                    'effect': effect
                })

        # Handle effect
        if effect == Effect.Food:
            # Increase starvation for food
            game_state['starvation'] = game_state.get('starvation', 0) + 1
            if (game_state['starvation'] > max_starvation):
                game_state['starvation'] = game_state['starvation'] - 1
        elif effect == Effect.Toxic:
            # Decrease starvation for toxic
            starvation = game_state.get('starvation', 0) - 1
            game_state['starvation'] = max(0, starvation)

            # Show message about toxic food
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            messagebox.showinfo("Отравление", "Вы съели несъедобное блюдо! Ваш голод понизился")
            root.destroy()

            # Check if starvation reached 0
            if starvation < 0:
                self._show_game_over(game_state)
                return

        # Increment rounds count
        if (increment_cost):
            game_state['money'] = game_state['money'] + item['cost']
            game_state['rounds_count'] = game_state['rounds_count'] + 1

            # Get next item
            self.set_new_item()
        print("starvation: " + str(game_state['starvation']))

    def load_image(self, image_path):
        if image_path not in self._cached_images:
            try:
                image = pygame.image.load(image_path)
                image = pygame.transform.scale(image, (200, 200))
                self._cached_images[image_path] = image
            except pygame.error as e:
                print(f"Error loading image: {e}")
                return
        return self._cached_images[image_path]

    def set_new_item(self):
        # Set loading state
        self.is_loading = True

        # Create a thread to fetch the item
        def fetch_item():
            # Check if we should use a cached item (20% chance if we have enough cached items)
            if len(self._cached_mappings) > 3 and random.random() < 0.2:
                # Get a random cached item from our history
                cached_entry = random.choice(self._cached_mappings)
                self.current_item = cached_entry['item']
            else:
                # Get a new random item
                self.current_item = items_provider.get_random_item()
            
            # Reset loading state
            self.is_loading = False

        # Start the thread
        threading.Thread(target=fetch_item).start()

    def update_loading_animation(self):
        # Update the loading animation frame
        if self.is_loading:
            current_time = pygame.time.get_ticks()
            if current_time - self.loading_animation_timer > 100:  # Change frame every 100ms
                self.current_loading_frame = (self.current_loading_frame + 1) % len(self.loading_frames)
                self.loading_animation_timer = current_time

    def draw_game_ui(self, screen, game_state):
        try:
            background = pygame.image.load('in-game-background.png')
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            screen.blit(background, (0, 0))
        except pygame.error as e:
            print(f"Could not load image: {e}")
            screen.fill(WHITE)

        if self.is_in_shop:
            return

        # Update loading animation if we're in loading state
        self.update_loading_animation()

        if self.is_loading:
            # Draw loading animation
            loading_frame = self.loading_frames[self.current_loading_frame]
            loading_rect = loading_frame.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            screen.blit(loading_frame, loading_rect)

            # Show loading text
            loading_text = self.FONT.render("Ищем что предложить попробовать...", True, BLACK)
            screen.blit(loading_text, (WIDTH // 2 - loading_text.get_width() // 2, HEIGHT // 2 + 60))
        elif self.current_item:
            item_name = self.current_item.get('name', 'Unknown Item')
            item_text = self.FONT.render(item_name, True, WHITE)

            # Create a black background rectangle for the item name
            text_bg_rect = item_text.get_rect(center=(WIDTH // 2, 70))
            # Add some padding around the text
            text_bg_rect.inflate_ip(20, 10)
            pygame.draw.rect(screen, BLACK, text_bg_rect)

            # Draw the text on top of the background
            screen.blit(item_text, item_text.get_rect(center=(WIDTH // 2, 70)))

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

    def _show_game_over(self, game_state):
        rounds_count = game_state.get('rounds_count', 0)
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showinfo("Проигрыш", f"Ты проиграл! Завершённые раунды: {rounds_count}\nИгра закроется, если хочешь начать сначала - перезапусти игру!")
        root.destroy()
        pygame.quit()
        import sys
        sys.exit()

