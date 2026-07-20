import random
import string

print("Hello, World!")

random_string = "".join(random.choices(string.ascii_letters + string.digits, k=32))
print(f"Random: {random_string}")
