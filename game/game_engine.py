import random
import pygame
from game.color_button import ColorButton
from game.sound_manager import SoundManager


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        pad_size = 130
        gap = 24
        start_x = width // 2 - pad_size - (gap // 2)
        start_y = 150

        self.buttons = [
            ColorButton(0, pygame.Rect(start_x, start_y, pad_size, pad_size), (110, 20, 20), (255, 50, 50)),                      # Red
            ColorButton(1, pygame.Rect(start_x + pad_size + gap, start_y, pad_size, pad_size), (15, 60, 150), (40, 170, 255)),   # Blue
            ColorButton(2, pygame.Rect(start_x, start_y + pad_size + gap, pad_size, pad_size), (15, 100, 30), (50, 255, 90)),    # Green
            ColorButton(3, pygame.Rect(start_x + pad_size + gap, start_y + pad_size + gap, pad_size, pad_size), (140, 110, 10), (255, 235, 40)), # Yellow
        ]

        self.sequence = []
        self.player_input = []
        self.score = 0

        self.state = "WATCH"
        self.showing_step = 0
        self.step_start_time = 0
        self.is_flashing = False
        self.round_lead_in = 500  # short breather before each round's playback starts

        # Task 2: playback speed. Both durations shrink by speed_factor every
        # round until they reach their minimums.
        self.base_flash_duration = 450
        self.base_pause_duration = 200
        self.min_flash_duration = 140
        self.min_pause_duration = 60
        self.speed_factor = 0.9
        self.flash_duration = self.base_flash_duration
        self.pause_duration = self.base_pause_duration

        self.player_lit_button = None
        self.player_lit_start = 0
        self.player_flash_duration = 150

        # Task 3: one tone per pad.
        self.sounds = SoundManager()

        # Task 4: time allowed for the player's whole turn. It grows with the
        # pattern length, so longer patterns get proportionally more time.
        self.turn_base_time = 2000
        self.turn_time_per_step = 900
        self.turn_time_limit = self.turn_base_time
        self.turn_time_left = self.turn_time_limit
        self.turn_start_time = 0
        self.timer_bar_rect = pygame.Rect(start_x, start_y + 2 * pad_size + gap + 22, 2 * pad_size + gap, 14)

        self.game_over_reason = ""

        self.font_title = pygame.font.SysFont(None, 40)
        self.font_medium = pygame.font.SysFont(None, 28)

        self.start_next_round()

    def start_next_round(self):
        new_color = random.randint(0, 3)

        # Task 1 fix: append exactly one new step. The old line,
        # `self.sequence += self.sequence + [new_color]`, appended a full copy
        # of the sequence as well, so the length went 1, 3, 7, 15, 31...
        self.sequence.append(new_color)

        round_number = len(self.sequence)

        # Task 2: speed up as the rounds advance.
        scale = self.speed_factor ** (round_number - 1)
        self.flash_duration = max(self.min_flash_duration, int(self.base_flash_duration * scale))
        self.pause_duration = max(self.min_pause_duration, int(self.base_pause_duration * scale))

        # Task 4: time budget for this round's turn.
        self.turn_time_limit = self.turn_base_time + self.turn_time_per_step * round_number
        self.turn_time_left = self.turn_time_limit

        self.player_input.clear()
        self.state = "WATCH"
        # Playback starts after round_lead_in; update() lights step 0 then.
        self.showing_step = -1
        self.step_start_time = pygame.time.get_ticks()
        self.is_flashing = False

    def light_button(self, btn):
        btn.is_lit = True
        self.sounds.play(btn.color_id)

    def dim_button(self, btn):
        btn.is_lit = False
        self.sounds.stop(btn.color_id)

    def update(self):
        now = pygame.time.get_ticks()

        if self.player_lit_button is not None:
            if now - self.player_lit_start >= self.player_flash_duration:
                self.dim_button(self.player_lit_button)
                self.player_lit_button = None

        if self.state == "WATCH":
            if self.is_flashing:
                if now - self.step_start_time >= self.flash_duration:
                    self.dim_button(self.buttons[self.sequence[self.showing_step]])
                    self.is_flashing = False
                    self.step_start_time = now
            else:
                wait = self.round_lead_in if self.showing_step < 0 else self.pause_duration
                if now - self.step_start_time >= wait:
                    self.showing_step += 1
                    if self.showing_step < len(self.sequence):
                        next_id = self.sequence[self.showing_step]
                        self.light_button(self.buttons[next_id])
                        self.is_flashing = True
                        self.step_start_time = now
                    else:
                        self.state = "PLAYER_TURN"
                        self.turn_start_time = now

        elif self.state == "PLAYER_TURN":
            # Task 4: count down, and end the game when the time runs out.
            self.turn_time_left = max(0, self.turn_time_limit - (now - self.turn_start_time))
            if self.turn_time_left <= 0:
                self.end_game("TIME'S UP!")

    def handle_event(self, event):
        if self.state == "GAME_OVER":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.reset()
            return

        if self.state == "PLAYER_TURN" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for btn in self.buttons:
                if btn.contains(event.pos):
                    # Dim the previous click first, otherwise two quick clicks
                    # on different pads leave the first one stuck lit.
                    if self.player_lit_button is not None:
                        self.dim_button(self.player_lit_button)

                    self.light_button(btn)
                    self.player_lit_button = btn
                    self.player_lit_start = pygame.time.get_ticks()

                    self.register_player_click(btn.color_id)
                    break

    def register_player_click(self, color_id):
        self.player_input.append(color_id)
        current_idx = len(self.player_input) - 1

        if self.player_input[current_idx] != self.sequence[current_idx]:
            self.end_game("WRONG PATTERN!")
            return

        if len(self.player_input) == len(self.sequence):
            self.score += 1
            self.start_next_round()

    def end_game(self, reason):
        self.state = "GAME_OVER"
        self.game_over_reason = reason
        self.sounds.play_error()

    def reset(self):
        self.sequence.clear()
        self.player_input.clear()
        self.score = 0
        for btn in self.buttons:
            btn.is_lit = False
        self.player_lit_button = None
        self.game_over_reason = ""
        self.start_next_round()

    def render_timer_bar(self, screen):
        fraction = self.turn_time_left / self.turn_time_limit

        if self.state != "PLAYER_TURN":
            fill_color = (90, 95, 105)      # idle while the pattern is shown
        elif fraction > 0.5:
            fill_color = (80, 240, 130)
        elif fraction > 0.25:
            fill_color = (255, 200, 60)
        else:
            fill_color = (240, 70, 70)

        track = self.timer_bar_rect
        pygame.draw.rect(screen, (45, 48, 58), track, border_radius=7)
        fill_width = int(track.width * fraction)
        if fill_width > 0:
            fill = pygame.Rect(track.x, track.y, fill_width, track.height)
            pygame.draw.rect(screen, fill_color, fill, border_radius=7)

        label_surf = self.font_medium.render(f"Time: {self.turn_time_left / 1000:.1f}s", True, (190, 195, 205))
        screen.blit(label_surf, (self.width // 2 - label_surf.get_width() // 2, track.bottom + 8))

    def render(self, screen):
        screen.fill((22, 24, 30))

        title_surf = self.font_title.render("Memory Pattern Arena", True, (245, 245, 245))
        screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 20))

        speed = self.base_flash_duration / self.flash_duration
        hud_text = f"Score: {self.score}    Round: {len(self.sequence)}    Speed: x{speed:.1f}"
        score_surf = self.font_medium.render(hud_text, True, (255, 220, 80))
        screen.blit(score_surf, (self.width // 2 - score_surf.get_width() // 2, 60))

        if self.state == "WATCH":
            status_text, status_color = "Watch the pattern...", (190, 195, 205)
        elif self.state == "PLAYER_TURN":
            status_text, status_color = "Your turn: Click the pattern!", (80, 240, 130)
        else:
            status_text, status_color = "Game over", (190, 195, 205)
        status_surf = self.font_medium.render(status_text, True, status_color)
        screen.blit(status_surf, (self.width // 2 - status_surf.get_width() // 2, 95))

        for btn in self.buttons:
            btn.render(screen)

        self.render_timer_bar(screen)

        if self.state == "GAME_OVER":
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            over_surf = self.font_title.render(f"{self.game_over_reason} GAME OVER", True, (240, 70, 70))
            screen.blit(over_surf, (self.width // 2 - over_surf.get_width() // 2, self.height // 2 - 40))

            final_score_surf = self.font_medium.render(f"Final Score: {self.score}", True, (255, 255, 255))
            screen.blit(final_score_surf, (self.width // 2 - final_score_surf.get_width() // 2, self.height // 2 + 10))

            restart_surf = self.font_medium.render("Press [R] to Play Again", True, (200, 200, 200))
            screen.blit(restart_surf, (self.width // 2 - restart_surf.get_width() // 2, self.height // 2 + 50))
