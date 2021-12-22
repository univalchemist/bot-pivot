import logging
from .style import style

class Logger():

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

class Logbook():

  def createINFOLogger(self):
    logger = logging.getLogger('INFO')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    file_handler = logging.FileHandler('INFO.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


  def createERRORLogger(self):
    logger = logging.getLogger('ERROR')
    logger.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    file_handler = logging.FileHandler('ERROR.log')
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger