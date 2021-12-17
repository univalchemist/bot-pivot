from .style import style

class logbook():

    def success(self, message):
        print(style().GREEN + message + style().RESET)
    def warning(self, message):
        print(style().YELLOW + message + style().RESET)
    def error(self, message):
        print(style().RED + message + style().RESET)
    def info(self, message):
        print(style().CYAN + message + style().RESET)
    def info_blue(self, message):
        print(style().BLUE + message + style().RESET)
    def info_magenta(self, message):
        print(style().MAGENTA + message + style().RESET)