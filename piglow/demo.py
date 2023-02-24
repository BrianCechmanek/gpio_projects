import piglow

piglow.clear_on_exit = True

if __name__ == "__main__":
    while True:
        piglow.red(64)

        piglow.show()

        piglow.auto_update = True


