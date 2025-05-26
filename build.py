print('-- pkg build --')
print('; updating requirements.txt')
import os
os.system('pip freeze > requirements.txt')