import sys

class Logger:
    # ANSI escape codes
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    C_DIM = "\033[2m"
    C_RED = "\033[31m"
    C_GREEN = "\033[32m"
    C_YELLOW = "\033[33m"
    C_BLUE = "\033[34m"
    C_MAGENTA = "\033[35m"
    C_CYAN = "\033[36m"
    C_GRAY = "\033[90m"

    @classmethod
    def info(cls, message: str):
        print(f"{cls.C_CYAN}[*] {message}{cls.C_RESET}")

    @classmethod
    def success(cls, message: str):
        print(f"{cls.C_BOLD}{cls.C_GREEN}[+] {message}{cls.C_RESET}")

    @classmethod
    def error(cls, message: str):
        print(f"{cls.C_RED}[!] {message}{cls.C_RESET}", file=sys.stderr)

    @classmethod
    def warn(cls, message: str):
        print(f"{cls.C_YELLOW}[!] {message}{cls.C_RESET}")

    @classmethod
    def dim(cls, message: str):
        print(f"{cls.C_DIM}{cls.C_GRAY}{message}{cls.C_RESET}")

    @classmethod
    def header(cls, message: str):
        print(f"{cls.C_BOLD}{cls.C_MAGENTA}=== {message} ==={cls.C_RESET}")

    @classmethod
    def separator(cls):
        print(f"{cls.C_YELLOW}" + "-" * 40 + f"{cls.C_RESET}")
