import time
import threading
from flask import Flask

someCringe = Flask(__name__)

def heavy_func():
    # time.sleep(3)
    print('Hi!')

@someCringe.route('/', methods=['GET'])
def get_method(): 
    return "Welcomeeeeee2!"

if __name__ == '__main__':
    print('lol')
    thread = threading.Thread(target=heavy_func)
    # thread.daemon = True         # Daemonize 
    thread.start()
    # app.run(host='0.0.0.0', debug=True, threaded=True),
