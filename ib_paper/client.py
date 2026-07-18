import socketio

sio = socketio.Client() 

sio.connect("http://localhost:8081")

sio.emit("subscribe_price", {"ticker": "AAPL"})

# sio.disconnect()