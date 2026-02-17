from typing import Callable

from nanoid import generate


def uuid(size=17) -> str:
    """
    Generate a random uuid string of the given size.
    """
    alphabet_set = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return generate(alphabet_set, size)


# Usage example
# ids = generate_ids()
# id1 = next(ids)
# id2 = next(ids)
# ...

# With a transformer
# ids = generate_ids(lambda id: f"prefix-{id}")
# id1 = next(ids)
# id2 = next(ids)
# ...


def generate_ids(transformer: Callable[[str], str] = lambda id: id):
    """
    A generator function for uuid
    """
    while True:
        yield transformer(uuid())
