import shutil
import subprocess

print('-- pkg build --')
print('; updating requirements.txt')

if shutil.which('pip') is None:
    print('❌ pip not found')
else:
    try:
        with open('requirements.txt', 'w') as f:
            subprocess.run(['pip', 'freeze'], stdout=f, check=True)
        print('requirements.txt updated successfully 🎉')
    except subprocess.CalledProcessError:
        print('❌ failed to update requirements.txt')
