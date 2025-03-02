1. Make a TCP Connection using ngrok and bind it to the port:8080 on the server

2. Change port number of tcp wherever we use socket.connect in both game 1 and game 2

3. In both game clients, update the host link to the ngrok link

4. Make sure fastapi and ngrok are on 2 different ports

`ngrok tcp 8080`