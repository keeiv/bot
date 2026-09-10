import os, socket, base64
os.environ['PYTHON_DOTENV_DISABLED']='1'
os.environ['GENSHIN_ENCRYPTION_KEY']=base64.urlsafe_b64encode(b'0'*32).decode()
for key in list(os.environ):
    if any(x in key for x in ('TOKEN','API_KEY','CLIENT_SECRET')):
        os.environ.pop(key,None)
_original_connect=socket.socket.connect
_original_connect_ex=socket.socket.connect_ex
def local_only(original):
    def wrapped(self, address):
        if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1','localhost'):
            raise RuntimeError('AUDIT: external network disabled')
        return original(self,address)
    return wrapped
socket.socket.connect=local_only(_original_connect)
socket.socket.connect_ex=local_only(_original_connect_ex)
