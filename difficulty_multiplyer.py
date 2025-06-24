def get_difficulty(game_rounds: int) -> int:
    print("Request to get difficulty for round " + str(game_rounds))
    if (game_rounds > 5):
        return 3
    elif (game_rounds > 10):
        return 4
    return 2