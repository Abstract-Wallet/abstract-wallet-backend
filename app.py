import time
import threading
import json
from flask import Flask, request
from flask_cors import CORS
from web3 import HTTPProvider
import os
import asyncio
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()


ENTRY_POINT = '0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789'
MY_TELEGRAM_ID = 327150749

ops_queue_json_sem = threading.Semaphore()
event_loop = asyncio.get_event_loop()
bot = Bot(os.environ['TELEGRAM_BOT_TOKEN'])

app = Flask(__name__)
CORS(app)

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
    print(f'Sent user op {op}. Response: {response}')

    if 'error' in response:
        raise Exception(f'Failed to send op. Error: {response["error"]}')
    

def check_ops_to_send():
    with ops_queue_json_sem:
        raw_ops_queue = get_current_queue()
        sorted_ops_queue = sorted(raw_ops_queue, key=lambda op: op['sendAt'])
        current_time = int(time.time())

        new_ops_queue = []
        ops_to_send = {} # In order to not spam the node, send one user op per wallet
        for op in sorted_ops_queue:
            if 'sendAt' not in op or 'sender' not in op or 'message' not in op or 'chainId' not in op or 'subscriptionId' not in op:
                print('Invalid op', op)
                continue

            if op['sendAt'] >= current_time:
                new_ops_queue.append(op)
                continue
            
            if op['sender'] not in ops_to_send:
                ops_to_send[op['sender']] = op
        
        with open('ops_queue.json', 'w') as f:
            f.write(json.dumps(new_ops_queue))
        
    bad_subscription_ids = []
    for op in ops_to_send.values():
        try:
            send_op(op)
            time.sleep(1)
        except Exception as e:
            print('Failed to send op.', op, e)
            bad_subscription_ids.append(op['subscriptionId'])
    
    if len(bad_subscription_ids) > 0:  # Remove all ops that are on a broken subscription
        with ops_queue_json_sem:
            raw_ops_queue = get_current_queue()
            new_ops_queue = []
            for op in raw_ops_queue:
                if op['subscriptionId'] not in bad_subscription_ids:
                    new_ops_queue.append(op)
            
            with open('ops_queue.json', 'w') as f:
                f.write(json.dumps(new_ops_queue))

def periodically_check_ops_to_send():
    while True:
        check_ops_to_send()
        time.sleep(5)

@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    return 'OK'

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

@app.route('/waitlist', methods=['POST'])
def waitlist():
    email = request.json['email']
    with open('waitlist.txt', 'a') as f:
        f.write(email + '\n')

    # Inform the admin about the new email
    event_loop.run_until_complete(bot.send_message(MY_TELEGRAM_ID, f'New email: {email}'))
    return 'OK'

if __name__ == '__main__':
    thread = threading.Thread(target=periodically_check_ops_to_send)
    thread.daemon = True         # Daemonize 
    thread.start()
    app.run(host='0.0.0.0', debug=False, threaded=True, port=5001),
