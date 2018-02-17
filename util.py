# -*- coding: utf-8 -*-
import os
import logging
from colored import fore, back, style


STY_DESC = fore.LIGHT_GREEN + back.BLACK
STY_DESC_INV = fore.BLACK + back.LIGHT_GOLDENROD_2B
STY_DESC_DEBUG = fore.SKY_BLUE_1 + back.BLACK + style.DIM
STY_USER = style.RESET + fore.WHITE + back.BLACK
STY_CURSOR = fore.LIGHT_GOLDENROD_2B + back.BLACK + style.BOLD
STY_RESP = fore.WHITE + back.MEDIUM_VIOLET_RED + style.BOLD
STY_RECIPIENT = fore.WHITE + back.DODGER_BLUE_2 + style.BOLD
STY_STAT_DATA = fore.WHITE + back.BLACK + style.BOLD
STY_STAT_LABEL = fore.SKY_BLUE_1 + back.BLACK
STY_INVISIBLE = fore.BLACK + back.BLACK
# STY_RESP = fore.WHITE + back.GREY_11 + style.BOLD #+ style.NORMAL


def setup_custom_logger(name):
    formatter = logging.Formatter(
        STY_DESC_DEBUG + '%(asctime)s - %(module)s - %(levelname)8s - %(message)s' +
            style.RESET, datefmt='%Y-%b-%d %H:%M:%S')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.WARN)
    logger.addHandler(handler)
    return logger


def clear_screen():
    """Simple cross-platform way to clear the terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')
 

def clean_input(u_input):
    """Fairly basic whitelisting based text cleaning function"""
    keepcharacters = (' ', '.', ',', ';', '\'', '?', '-')
    return ''.join(
        c for c in u_input if c.isalnum() or
        c in keepcharacters).rstrip()
