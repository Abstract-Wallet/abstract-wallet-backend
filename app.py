import time
import threading
import json
from flask import Flask, request
from web3 import HTTPProvider
import os

ENTRY_POINT = '0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789'
ops_queue_json_sem = threading.Semaphore()

app = Flask(__name__)

base_mainnet_rpc = 'https://base-mainnet.g.alchemy.com/v2/y74PPMkNGcWpxnIbVFWvp7sLE-1Miuyy'
base_goerli_rpc = 'https://base-goerli.g.alchemy.com/v2/PyhX0B5YxLRdSDob7vZ3wlRVv_WVFjwc'

def get_current_queue():
    if not os.path.exists('ops_queue.json'):
        with open('ops_queue.json', 'w') as f:
            f.write('[]')

    with open('ops_queue.json') as f:
        return json.loads(f.read())

def send_op(op: dict):
    if op['chainId'] == 8453:
        rpc = base_mainnet_rpc
    elif op['chainId'] == 84531:
        rpc = base_goerli_rpc
    else:
        raise Exception('Invalid chainId')
    
    provider = HTTPProvider(rpc)
    response = provider.make_request('eth_sendUserOperation', params=[op['message'], ENTRY_POINT])
    print(f'Sent user op {op}. Response:', response)
    

def check_ops_to_send():
    with ops_queue_json_sem:
        raw_ops_queue = get_current_queue()
        sorted_ops_queue = sorted(raw_ops_queue, key=lambda op: op['sendAt'])
        current_time = int(time.time())

        ops_to_send = []
        new_ops_queue = []
        for op in sorted_ops_queue:
            if current_time >= op['sendAt']:
                ops_to_send.append(op)
            else:
                new_ops_queue.append(op)
        
        with open('ops_queue.json', 'w') as f:
            f.write(json.dumps(new_ops_queue))

    for op in ops_to_send:
        try:
            send_op(op)
        except Exception as e:
            print(f'Failed to send op {op}:', e)


def periodically_check_ops_to_send():
    while True:
        check_ops_to_send()
        time.sleep(3)

@app.route('/new-user-ops', methods=['POST'])
def receive_new_user_ops():
    with ops_queue_json_sem:
        raw_ops_queue = get_current_queue()
        
        new_ops = request.json['newOps']
        raw_ops_queue.extend(new_ops)
        with open('ops_queue.json', 'w') as f:
            f.write(json.dumps(raw_ops_queue))
    
    print(f'Added {len(new_ops)} new ops to queue')
    return 'OK'

if __name__ == '__main__':
    thread = threading.Thread(target=periodically_check_ops_to_send)
    thread.daemon = True         # Daemonize 
    thread.start()
    app.run(host='0.0.0.0', debug=False, threaded=True, port=5001),
