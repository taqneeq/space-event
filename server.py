import os
import time
import uvicorn
import asyncio
import socket
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from threading import Thread

# Global scores dictionary and player slots tracking
scores = {"player_1": "0", "player_2": "0"}  # Changed from player1/player2 to player_1/player_2

async def handle_tcp_connections(websockets_set):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', 8080))
    server.listen(5)
    server.setblocking(False)

    while True:
        try:
            client_socket, _ = await asyncio.get_event_loop().sock_accept(server)
            data = await asyncio.get_event_loop().sock_recv(client_socket, 1024)
            
            if data:
                message = data.decode('utf-8').strip()
                
                # Remove the slot request handling since we're using fixed IDs
                if ":" in message:
                    # Handle score updates
                    player_id, score = message.split(':')
                    if player_id in ["player_1", "player_2"]:  # Verify valid player ID
                        scores[player_id] = score
                        
                        # Broadcast scores to all connected WebSocket clients
                        disconnected = set()
                        for websocket in websockets_set:
                            try:
                                await websocket.send_json(scores)
                            except WebSocketDisconnect:
                                disconnected.add(websocket)
                        
                        # Remove disconnected clients
                        websockets_set -= disconnected

            client_socket.close()
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
            await asyncio.sleep(0.1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create a set to store WebSocket connections
    if not hasattr(app, 'websockets'):
        app.websockets = set()
    
    # Start TCP server in the background
    tcp_task = asyncio.create_task(handle_tcp_connections(app.websockets))
    
    yield
    
    # Cleanup on shutdown
    tcp_task.cancel()
    try:
        await tcp_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    app.websockets.add(websocket)
    
    try:
        while True:
            message = await websocket.receive_text()
            if message == "reset":
                # Broadcast reset command to all clients
                for ws in app.websockets:
                    await ws.send_text("reset_acknowledged")
    except WebSocketDisconnect:
        app.websockets.remove(websocket)

html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Space Obstacle Game Scoreboard</title>
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap");

      body,
      html {
            margin: 0;
            padding: 0;
            height: 100%;
        font-family: "Press Start 2P", cursive;
            background-color: #000033;
            color: #ffffff;
            overflow: hidden;
        }

        .stars {
            position: absolute;
            width: 1px;
            height: 1px;
            background: white;
            z-index: 1;
        }

        .container {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100%;
            position: relative;
            z-index: 2;
        }

        .logo {
        width: 400px;
        height: 400px;
            margin-bottom: 30px;
            display: flex;
            justify-content: center;
            align-items: center;
      }

      .logo svg {
        width: 100%;
        height: 100%;
        }

        .scoreboard {
            display: flex;
            justify-content: space-around;
            align-items: center;
            width: 100%;
        }

        .score-container {
            text-align: center;
        }

        .score {
            font-size: 4em;
            margin: 20px 0;
            text-shadow: 0 0 10px #00ffff;
        }

        .player-name {
            font-size: 1.5em;
            color: #00ffff;
        }

        .reset-btn {
        font-family: "Press Start 2P", cursive;
            font-size: 1.2em;
            padding: 15px 30px;
            background-color: #ff00ff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s;
            animation: pulse 2s infinite;
            margin-top: 30px;
        }

        .reset-btn:hover {
            background-color: #ff66ff;
            transform: scale(1.1);
        }

        @keyframes pulse {
        0% {
          transform: scale(1);
        }
        50% {
          transform: scale(1.1);
        }
        100% {
          transform: scale(1);
        }
        }

        .spaceship {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 2em;
            animation: fly 5s infinite;
        }

        @keyframes fly {
        0% {
          transform: translateX(-50%) translateY(0);
        }
        50% {
          transform: translateX(-50%) translateY(-20px);
        }
        100% {
          transform: translateX(-50%) translateY(0);
        }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
        <svg
          version="1.1"
          viewBox="0 0 1600 1441"
          width="526"
          height="474"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            transform="translate(675,325)"
            d="m0 0h53l258 1 13 2 4 5 6 19v12l-6 10-12 12-11 9-12 11-11 9-14 11-15 13-16 12-6 4-6 1-23 1-88 1-1 1-1 11v80l10-4 30-15 20-8 20-6 31-6 21-3 21-1h22l20 1 29 4 30 7 16 5 27 11 17 8 20 12 16 12 11 8 10 10 8 7 10 10 7 8 9 10 13 18 11 16 12 23 9 20 7 19 6 25 5 25 3 33v26l-2 20-5 14-6 12-11 12-9 8-10 6-17 5-15 1-13-1-15-4-11-6-12-10-7-8-7-10-6-15-2-10-2-32-3-25-4-18-6-15-8-17-8-13-6-9-10-11-9-11-10-7-15-10-16-9-21-7-16-4-16-2h-25l-20 3-24 7-12 5-17 11-13 10-9 8-9 11-12 15-8 14-8 20-5 18-2 15v28l2 19 5 19 8 21 8 14 11 14 11 12 8 8 19 14 15 9 10 5 26 10 19 6 16 4 15 6 9 6 11 12 8 12 6 17 1 8v15l-2 14-5 12-9 13-13 13-13 8-10 4-12 2h-20l-22-3-25-6-24-8-22-9-16-8-19-11-14-10-10-8-13-10-13-12-8-7-6 1-14 10-7 4-6 2h-26l-10-5-22-16-13-10-15-10-12-7-6-5-4-10-1-8-1-54v-171l1-15 3-9 4-6 11-8 13-10 7-5 1-6-12-8-14-9-8-6-4-5-1-5-1-186-1-5-65 1h-34l-15-1-7-3-16-12-14-12-13-12-11-9-12-11-13-10-16-15-4-7-2-5v-7l5-18 6-8 5-2z"
            fill="#C01011"
          />
          <path
            transform="translate(675,325)"
            d="m0 0h53l258 1 13 2 4 5 6 19v12l-6 10-12 12-11 9-12 11-11 9-14 11-15 13-16 12-6 4-6 1-23 1-88 1-1 1-1 11v80l10-4 30-15 20-8 20-6 31-6 21-3 21-1h22l20 1 29 4 30 7 16 5 27 11 17 8 20 12 16 12 11 8 10 10 8 7 10 10 7 8 9 10 13 18 11 16 12 23 9 20 7 19 6 25 5 25 3 33v26l-2 20-5 14-6 12-11 12-9 8-10 6-17 5-15 1-13-1-15-4-11-6-12-10-7-8-7-10-6-15-2-10-2-32-3-25-4-18-6-15-8-17-8-13-6-9-10-11-9-11-10-7-15-10-16-9-21-7-16-4-16-2h-25l-20 3-24 7-12 5-17 11-13 10-9 8-7 8h-6l2-7 1-2-2-1-2-4v-8l-6 1-1-4h-3l-3-5-2-5-4-4-4-16-3-5v-2l-5-1-7-11v-5l-5-3-1-2-5-3h-10l-6-3-4-13-2-7-1-15-1-7-2-4-2-1v-5l-2-1 1-2h-2l-1 8-3 3h-2l-2-10v-15h-2v-27l-1-4-2 1-4-16-1-3-3-2 1-3h-9l-9-6 1-4h-3l-3-4-1-10-1-7-5-4v-6l-5-1v-2h-2l-1 2-1-2 2-5h-11l-10-7-3-2h2v-2l-11-1-9-5-11-8-3-5-5-4-4-9-3-6 1-8-6-15-2-6-2-9-3-2-7-2-5-4-1-6h2v-5l3-2-3-2 1-1-47-1v-1z"
            fill="#A40C1B"
          />
          <path
            transform="translate(940,507)"
            d="m0 0h22l20 1 29 4 30 7 16 5 27 11 17 8 20 12 16 12 11 8 10 10 8 7 10 10 7 8 9 10 13 18 11 16 12 23 9 20 7 19 6 25 5 25 3 33v26l-2 20-5 14-6 12-11 12-9 8-10 6-17 5-15 1-13-1-15-4-11-6-12-10-7-8-7-10-6-15-2-10-2-32-3-25-4-18-6-15-8-17-8-13-6-9-10-11-9-11-10-7-15-10-16-9-21-7-16-4-16-2h-25l-20 3-24 7-12 5-17 11-13 10-9 8-7 8-9 11-12 15-8 14-8 20-5 18-2 15v28l2 19 5 19 8 21 8 14 11 14 11 12 8 8 19 14 15 9 10 5 26 10 19 6 16 4 15 6 9 6 11 12 8 12 6 17 1 8v15l-2 14-5 12-9 13-13 13-13 8-10 4-12 2h-20l-22-3-25-6-24-8-22-9-16-8-5-3v-3l-2-4 7-1v-4h2l1-3h2v-4h2l1-11 3-8 4-12 6-7 5-9 8-11 3-5 5-5 7-11 3-4 4-6 7-7 2-4 7-3 10-1z"
            fill="#161E86"
          />
          <path
            transform="translate(591,740)"
            d="m0 0h1l1 130 1 22 2-2 4 2 1 9 2 7 2 3 3-1 4-8 8-7 5-2 5 4 4-2h11l10-6 3-5 4-1v2l4 1-1 2-3 4h5l-1 3h10v2l5-2 1 2-3 5 7-1 1 2 3-1 1 2 5-3v2h11l-1 3 4-2 19-11h-4v-2l4-2 2-6 3-4-1-4 5-1 1 3 9-1h7l5 1v-2l-2-1 3-5h-2l-1-8h2l2-7 3-2h2l1 5h2v-3h2l1-20h1l1 10 2-19h1l1 19 2 13 1 1 1-9 1-37 1-13h1l1-10 4 2 2-11 3-2v36l2 19 5 19 8 21 8 14 11 14 11 12 8 8 19 14 15 9 10 5 26 10 19 6 16 4 15 6 9 6 11 12 8 12 6 17 1 8v15l-2 14-5 12-9 13-13 13-13 8-10 4-12 2h-20l-22-3-25-6-24-8-22-9-16-8-19-11-14-10-10-8-13-10-13-12-8-7-6 1-14 10-7 4-6 2h-26l-10-5-22-16-13-10-15-10-12-7-6-5-4-10-1-8-1-54z"
            fill="#880A3D"
          />
          <path
            transform="translate(970,775)"
            d="m0 0h19l15 3 12 5 9 7 15 16 12 13 8 10 11 11 9 11 14 14 7 8 13 15 13 14 9 11 11 12 9 11 18 18 10 13 8 15 3 12v21l-3 12-8 16-9 12-9 9-16 8-11 4-12 2h-13l-14-3-18-8-10-9-12-12-7-8-9-10-7-8-15-16-5-6-8-7-9-11-12-12-9-11-16-17-11-13-9-9-7-8-6-7v-2l-4-2-10-12-4-8-3-7-3-13v-20l3-14 4-12 7-10 9-10 9-8 13-6 12-3z"
            fill="#1D0D8F"
          />
          <path
            transform="translate(1178,648)"
            d="m0 0 5 2v2l3-2 7-1 7 3 4 5v2l4 2 4 5 8 13 3 6v3l3 1v4h2l2 6 4-1 2 4 1 4 3-1 6 18 8 38 3 24 1 14v26l-2 20-5 14-6 12-11 12-9 8-10 6-17 5-15 1-13-1-15-4-11-6-12-10-7-8-7-10-6-15-2-10-2-32-3-25-3-14-1-10-5-10-2-10-2-5-6-7-1-4-2-16-2-7 1-6 2-1-1-3 2-2 4 2 11-3 3 2h2l1 2h8 3l4 2 4-1 11-5 2-2 2-7 3-4 2-6 5-2v-5l10 1 3 1-2-5 6-1h8l2-7z"
            fill="#1D0D8F"
          />
          <path
            transform="translate(734,326)"
            d="m0 0h252l13 2 4 5 6 19v12l-6 10-12 12-11 9-12 11-11 9-14 11-15 13-16 12-6 4-6 1-23 1h-89l1-3-4-4-3-8-3-7-1-2v-12l-1-2v-13l-2-4-5-1v-6l-5-5-2-4 2-6v-8l-4-7-1-6v-8l4-6v-11l2-1-2-4-30-2z"
            fill="#691046"
          />
          <path
            transform="translate(894,950)"
            d="m0 0 10 3 15 6 19 6 16 4 15 6 9 6 11 12 8 12 6 17 1 8v15l-2 14-5 12-9 13-13 13-13 8-10 4-12 2h-20l-22-3-25-6-24-8-22-9-16-8-5-3v-3l-2-4 7-1v-4h2l1-3h2v-4h2l1-11 3-8 4-12 6-7 5-9 8-11 3-5 5-5 7-11 3-4 4-6 7-7 2-4 7-3 10-1z"
            fill="#1D0D8F"
          />
          <path
            transform="translate(794,758)"
            d="m0 0 1 3 2 1v2h2l-2 12-3 4-2 11h-3l-1-1-1 10h-1l-1 12-1 42-1 5-3-2-3-19-2 13-3 3h-2v3l-3 1v-6l-4 3v2h-2l-1 4h-2l1 8h2l-2 5 1 3h-17l-7 1 2-1-5-2 2 5h-2l-4 10-4 1v2l5-1-3 3-17 10-2 2-3-1 1-2h-11l-1-1-5 2v-2l-3 1-1-2-4 1-2-1 2-6-5 1-1 2v-3l-9-1v-2l-4-1 2-5 1-1-3-1v-2l-5 3-3 5-9 5h-11l-4 2-5-4-5 2-6 6h-2l-2 6-3 4-4-2-2-4-1-9v-3l-2-1-1-1h-2l-2 2-1-24v-24l2 2 1-16 5-11h7l1-5 2-7 1-7 3-2 1 4 1-12 3-3 3 1 2 7v11l3 8 5-1-1-3 1-5v-9l1 3 1-2 2-7 1-2 1-6 2 3v5h2l2 4 3 1 2-2 1-10v-5l2-3h6l3 3 2 4 5-1h7l1 3 3-6 6-2 1-2h3v2l5 2 4-1 2 13 1 4 5 2 2 5 6-3h2l2-8 3-4 2 2 4-11 5 1 2 16h1l2-9 2-1 1-7 3-2 2 4 2-2 3 3 1 6 1 1 3 40 2-7 2-32 2-7 1-3 3-1 1-5h2l1 2h3v2h2v-3l6-1 4 2 1-5 6-11z"
            fill="#880A28"
          />
          <path
            transform="translate(825,900)"
            d="m0 0 5 1 11 12 8 8 19 14 15 9 11 6-1 2-10 1-7 2-2 5-8 8-3 6-5 6-4 7-4 5-3 2-5 9-5 6-6 11-3 1-3 10-3 6-2 8-1 8-1 2h-2v4h-2l-1 4-2-1v4l-6 2 3 5-6-1-16-10-17-13-14-11-13-12-8-7-6 1-5 3h-4v-16l1-1v-9l3-7 2-6 3-7 6-11 3-3 4-6 4-1 1-4 4-1 2-4 8-6 4-4 13-10h2l2-4 3-3h2v-3l5-3h2l1-3 11-6 13-4z"
            fill="#5D085A"
          />
          <path
            transform="translate(940,507)"
            d="m0 0h22l20 1 29 4 30 7-1 2-14 3-5 5-1 4h-3l-2 9-3 7-5 8-6 11-4 7v10l-3 7-3 5-3 3-1 5-1 3v7l1 4-1 8v17h-2l1 3h-4v2h-2v2l-19-2h-34l-2-12-3-17-2-4-3-30v-17l-1-3v-10l-2-12-2-7v-10l-1-13 2-3 7-3z"
            fill="#4C245D"
          />
          <path
            transform="translate(784,460)"
            d="m0 0 1 2h2v88l10-4 30-15 20-8 20-6 31-6 13-2h5l-1 2h-3l-1 8 1 9v9l3 10 1 9v11l1 4v16l3 29 2 4 3 17 1 3v9l2 1-16 3-21 6-12 5-11 7-2-1 2-5 2-1 2-6-3-1-3-5v-5h-2l-3-9-4-6-6-23-2-3-1-8-4-8-1-6-3-7-5-24-3-9-5-3h-8l-1 3-6 1h-3l-4-1v2l-8 3v6l-10-3-2-5-1-39z"
            fill="#7D0B2D"
          />
          <path
            transform="translate(384,326)"
            d="m0 0h65l10 1 7 4h3v7h-2v2h-4l1 4 7 1 19 5 6 3 2 2-1 6-1 5 2 5 7 13-1 19-1 9 2 1h-2v2h-2l-2 5h-5l-1 3-3 1-3 3-2 1h-10l-12-3-8 1-5-3h-4l1 7-1 3h2l1-2 1 5h2l2 6-8-6-20-18-11-9-12-11-13-10-16-15-4-7-2-5v-7l5-18 6-8z"
            fill="#D4120F"
          />
          <path
            transform="translate(906,328)"
            d="m0 0h93l4 5 6 19v12l-6 10-12 12-11 9-12 11-11 9-14 11-15 13-15 11-6 1-5 1 1-3-2-1v-4l2-13-1-2-4 1-6-7v-2l-3-1-4-9 1-10 5-6-6-2-2-6 1-7 5-14 4-10 3-4 2-8h2l-1-12 4-1v-2z"
            fill="#530945"
          />
          <path
            transform="translate(705,327)"
            d="m0 0h39l20 1 1 4 2 1-3 1 1 12-4 5v8l2 7 3 6v8l-2 7 4 6 3 2-1 6 5 1 3 4v14l1 5v8l3 5 3 9v3l4 2 1 3-3 7h-2v54l1 31 1 4 7 2 6 3-2 1 1 4-2 12-1 3h-2l-1 2-3-3-1-3-2-1v-4l-3 1v-24h-2l-1 9h-2l-2-16 2-4v-5l-2-2-1-5v-8l1-5-1-9-2-8-4-9-3-7-4-8-6-8-6-4-8-10-1-2-7-4v-2h-2l-4-4-4-3v-2l-5-2-6-5-5-5-5-3v-2l-3-1-4-4-6-3-4-5-2-5-2-6v-6l-1-3 1-9 3-7 4-10v-8l2-1 1-5h-2l1-6 3-1-2-3z"
            fill="#920E23"
          />
          <path
            transform="translate(808,882)"
            d="m0 0 7 2 1 2 5 3 7 10-3 2-11 2-10 4-10 5-3 3-5 2v3l-4 1-2 4-3 3-9 7-5 4h-2l-2 4-8 6-3 3h-2l-1 4-5 3-4 7h-2l-2 5-3 6-6 14-1 6h-2l1 9-1 4-1 13 3 1-12 9-9 3-15-1-11-5v-2h-3l1-3-3-8 1-5 1-7-1-5 3-6 1-1 1-8 3-1 1-5 5-6 2-9h2l1-4h2v-3h2l1-4 5-7 5-3 4-7h2l2-5 5-5 2-4 8-4 7-3 3-5 6-5h3l2-5 5-1 1-5 8-4 9 1 1-2 2 1 6-3h16z"
            fill="#6A0F45"
          />
          <path
            transform="translate(734,326)"
            d="m0 0h76l47 1v1l-19 1-6 4-3 3 1 5-4 10-3 8v15l2 3-1 7-1 3 1 2-1 4 2 9 2 3v10l4 2 2 6 3 5 1 5 3 7v5h-2v7l-5 3h28l4 2h-77l1-3-4-4-3-8-3-7-1-2v-12l-1-2v-13l-2-4-5-1v-6l-5-5-2-4 2-6v-8l-4-7-1-6v-8l4-6v-11l2-1-2-4-30-2z"
            fill="#730A2F"
          />
          <path
            transform="translate(795,778)"
            d="m0 0h1v36l2 19 5 19 8 21 7 12v2l-3-1v-2l-7-1-11 5h-16l-7 3h-2l-6 1-3-1-6 3h-2l-1 5-4 1-3 5-5 3-5 4-2 5-7 2-6 3h-2l-1 4-5 5-3 5h-2l-2 5-9 9-4 7h-2v3l-2 1-1 3h-2l-1 9-6 7v5h-4v8l-3 4-1 6 1 6-1 5h-2l4 11-1 2-1 1h3v2l5 1 6 3 13 1v1h-24l-10-5-22-16-6-5-2-6h2v-2h2l1-4-2-3h3v-4h3l1-4 6-3 1-7 5-8 8-10h3l2-7 1-7 3-1 3-13 2-7h2l1-2h2l2-4 4-4h2l2-10 13-1-1 3 4-2 19-11h-4v-2l4-2 2-6 3-4-1-4 5-1 1 3 9-1h7l5 1v-2l-2-1 3-5h-2l-1-8h2l2-7 3-2h2l1 5h2v-3h2l1-20h1l1 10 2-19h1l1 19 2 13 1 1 1-9 1-37 1-13h1l1-10 4 2 2-11z"
            fill="#7B0741"
          />
          <path
            transform="translate(686,776)"
            d="m0 0h3v2l5 2 4-1 2 13 1 4 5 2 2 5 6-3h2l2-8 3-4 2 2 4-11 5 1 1 4v11l-2-2-4 1-3 16-2 1-1-2-2 4-1 20-2 2-1-21-1-4-1 1-1 14v9l-4 1-1-5h-2l-1-7-4 1-3-3-3-8-3-2-3 1v-2l-4 1-3 9-2 9-4 1-1-4-7 3-2-3-4 5-3 9-4 5h-6l-2 4-4 6-1 4-7 6-8 8h-3l-2 5-5 5h-3v2l-6 3-7 7-3-3h-2l-2 2-1-24v-24l2 2 1-16 5-11h7l1-5 2-7 1-7 3-2 1 4 1-12 3-3 3 1 2 7v11l3 8 5-1-1-3 1-5v-9l1 3 1-2 2-7 1-2 1-6 2 3v5h2l2 4 3 1 2-2 1-10v-5l2-3h6l3 3 2 4 5-1h7l1 3 3-6 6-2 1-2h3v2l5 2 4-1 2 13 1 4 5 2 2 5 6-3h2l2-8 3-4 2 2 4-11 5 1 2 16h1l2-9 2-1 1-7 3-2 2 4 2-2 3 3 1 6 1 1 3 40 2-7 2-32 2-7 1-3 3-1 1-5h2l1 2h3v2h2v-3l6-1 4 2 1-5 6-11z"
            fill="#A50C1B"
          />
          <path
            transform="translate(1040,520)"
            d="m0 0 8 1 17 6 26 11 19 10 6 4-1 2-9-1-10-5-5-2-4-1-9 2-8 8-6 9-4 5-2 4-3 3-4 10-7 14h-2l-1 4-8 2v2l-7 3-4 3-3 2v3l-2 12-3 7-1 12-3 10-11-3-18-5-2-1v-2h2v-2l3-1v-2h2l-1-8v-12l1-6-1-3v-7l2-5 1-5 3-3 3-4 2-7v-9l7-12 3-6 3-4 4-7 3-8-2-1 2-1 1-3h3l1-5 3-1 2-4z"
            fill="#1D0D8F"
          />
          <path
            transform="translate(859,931)"
            d="m0 0 5 1 17 11 13 7-1 2-10 1-7 2-2 5-8 8-3 6-5 6-4 7-4 5-3 2-5 9-5 6-6 11-3 1-3 10-3 6-2 8-1 8-1 2h-2v4h-2l-1 4-2-1v4l-6 2 3 5-6-1-16-10-17-13-1-4 6-2 6-11 2-1 5-18 5-10 5-4 3-3 4-2 8-11 4-8 9-8 5-5 2-3h2l3-9 3-4h2l2-6 10-8z"
            fill="#3C0777"
          />
          <path
            transform="translate(735,328)"
            d="m0 0h29l1 4 2 1-3 1 1 12-4 5v8l2 7 3 6v8l-2 7 4 6 3 2-1 6 5 1 3 4v14l1 5v8l3 5 3 9v3l4 2 1 3-3 7h-7l-14-14-9-6v-2l-5-2v-3l-2-1v-3l-4-2-3-3v-2h-2l-1-2-5-3-8-11-6-8-4-7v-3l1-4 2-4-2-2v-7l2-3v-6h3l-1-7 1-6 3-2v-4h2v-11l2-3h2l1-2z"
            fill="#870A28"
          />
          <path
            transform="translate(840,924)"
            d="m0 0h13l8 6-2 2-7 2-6 6h-2l-1 4-1 2h-2l-2 4-4 9h-2l-2 4-4 2-2 4-7 6-5 9-8 11-6 2-2 4-4 3-5 12-4 15-3 2-6 12h-6l-1 2-12-9-6-5v-7l4-9h2l-1-5 4-4 5-15 2-5 6-8 2-2 2-1 3-9 8-9 9-6 7-6 5-3 8-5 5-7 4-2h4v-2z"
            fill="#4A0662"
          />
          <path
            transform="translate(858,327)"
            d="m0 0 9 1v2h-3l-2 5v9l-2 8-4 7h2l1 7-2 6 1 13-2 5 2 5v8l3 4v11l4 5 1 5 4 1 4 8-1 8 1 2h-6l-1 2h-4l-1 3h-24l-1-4 1-3h2l-3-10-2-4-1-4-3-5-2-6-2-1-1-10-2-5-2-8 1-4-1-2 2-5-1-5-1-6v-11l4-10 3-9-1-4 8-7 2-1z"
            fill="#650838"
          />
          <path
            transform="translate(999,511)"
            d="m0 0 12 1 30 7-1 2-14 3-5 5-1 4h-3l-2 9-3 7-5 8-6 11-4 7v10l-3 7-3 5-3 3-1 5-1 3v7l1 4-1 8v17h-2l1 3h-4v2h-2v2l-19-2h-34l-2-12-3-17-2-4-3-30v-17l-1-3v-10l-2-12-2-7v-10l-1-13 2-3 7-3z"
            fill="#3D2465"
          />
          <path
            transform="translate(911,509)"
            d="m0 0h5l-1 2h-3l-1 8 1 9v9l3 10 1 9v11l1 4v16l3 29 2 4 3 17 1 3v9l2 1-14 2v-2l-6-1-4-2-3-6-7-26-1-17-4-14-2-12-2-2-1-10-2-10-1-12 1-7v-10h-2l-1-4h-2v-2l21-4z"
            fill="#6A0F45"
          />
          <path
            transform="translate(940,507)"
            fill="#650838"
          />
          <path
            transform="translate(999,511)"
            d="m0 0 12 1 30 7-1 2-14 3-5 5-1 4h-3l-2 9-3 7-5 8-6 11-4 7v10l-3 7-3 5-3 3-1 5-1 3v7l1 4-1 8v17h-2l1 3h-4v2h-2v2l-19-2h-34l-2-12-3-17-2-4-3-30v-17l-1-3v-10l-2-12-2-7v-10l-1-13 2-3 7-3z"
            fill="#3D2465"
          />
          <path
            transform="translate(911,509)"
            d="m0 0h5l-1 2h-3l-1 8 1 9v9l3 10 1 9v11l1 4v16l3 29 2 4 3 17 1 3v9l2 1-14 2v-2l-6-1-4-2-3-6-7-26-1-17-4-14-2-12-2-2-1-10-2-10-1-12 1-7v-10h-2l-1-4h-2v-2l21-4z"
            fill="#6A0F45"
          />
          <path
            transform="translate(940,507)"
            d="m0 0h22v1l-14 1 1 4-3 2-1 7-4 6 1 6-1 5v11l1 2v16l1 1v13l-1 8 2 15 1 13 2 6v10l-1 6-2 2-2 5h15v1l-31 1-2-12-3-17-2-4-3-30v-17l-1-3v-10l-2-12-2-7v-10l-1-13 2-3 7-3z"
            fill="#591D54"
          />
          <path
            transform="translate(686,810)"
            d="m0 0h2v2l4-2v2l4 2 2 9h6l1-4v11h2l4 10-1 11-3 7-2-3v-2h-3l-2 6-5 1-2-4-3 1-2-1v2h-2l-2 4-7 1h-9l-5 6-2 4-2 11-5 7-9 5h-11l-4 2-5-4-5 2-6 6h-2l-2 6-3 4-4-2-2-4-1-11 3-7h3l4-3h3v-2l5-3 4-5 1-2h3l1-3 5-3 7-8h2l1-6 6-8 7-2 4-7 2-6 4-5 2 3 7-2 1 4 3-1 3-13 3-5z"
            fill="#920D22"
          />
          <path
            transform="translate(687,616)"
            d="m0 0 4 5 4-1 3 1v9h2l2 3 2 1v2l4 1 1 2 2 2-1 2 4 1-3 1-1 6-7 1-4 6-5 1v10h3l1 9 3 10v-7l-2-4 1-8 6-6 3 1 2-3 6-1 8 13 1 14h3l2 4h7l5 5 3 8v7l-5 8-4 2-6 7-2 2-5 2h-4l-2-4-2-5-3-7-3 1-2-10-3-1-1-5-2 4 6 15v6l-5-3-5-10-2-2-8-29-1-4-2-1 1-4-2-4-1-5v-3-2l3-3v-3h3v-5h-2v-4l4-7-1-5-3 1-3 6h-2l-1 5-2 1v-7l-3 3v-11l1 3h2v-6l5-5h2z"
            fill="#D4120F"
          />
          <path
            transform="translate(872,516)"
            d="m0 0 7 1 1 4h2l1 10-1 8 1 14 2 9 1 8 2 2 3 15 3 11 1 17 7 26 2 6 10 3v2l-24 7-2-5-4-4-3-12-5-12-4-9-3-6-3-17-2-17v-18l-4-16-2-6-1-9 2-4-8 1 2-4z"
            fill="#730A30"
          />
          <path
            transform="translate(824,540)"
            d="m0 0 6 1 4 5 4 16 3 15 4 11 3 9 1 1 2 10 3 8 5 18 4 6 1 7h2l2 6 2 4 2 1-2 7-5 8-16 12-1-3 2-4 1-9-2-9-4-10-2-7-6-8-6-12-6-9 1-18-2-2-2-7-2-2-1-12-6-9-7-1-2-2v-6l-2-1h2v-3l2-1 2-5 4-1 6-1 1-2z"
            fill="#910D23"
          />
          <path
            transform="translate(734,326)"
            d="m0 0h76v1h-6l-1 2-11 5-4 13-1 7v10l-2 4 2 7v7l-1 5 5 11 2 13 1 8 5 11 4 11v6l4 4-6 2 5 1v1h55l4 2h-77l1-3-4-4-3-8-3-7-1-2v-12l-1-2v-13l-2-4-5-1v-6l-5-5-2-4 2-6v-8l-4-7-1-6v-8l4-6v-11l2-1-2-4-30-2z"
            fill="#7D0A2D"
          />
          <path
            transform="translate(731,787)"
            d="m0 0h1l1 8 1 1-1 11h-1v61l-9 3h-12v2l-5 3-8 6-2 3-8 2-11 8h-11v-2l-4-1 2-5 1-1-3-1v-2l-3 1 1-11 5-8 3-3h14l4-4h2v-2h5l2 3h5l2-6h3l2 2 2-4 1-12-1-4 2-1v-16l1-7 3-4 1 7 1 16 1-19h2l1-5 2 4 3-16 4-1z"
            fill="#880A28"
          />
          <path
            transform="translate(794,758)"
            d="m0 0 1 3 2 1v2h2l-2 12-3 4-2 11h-3l-1-1-1 10h-1l-1 12-1 42-1 5-3-2-3-19-2 13-3 3h-2v-3l-2-1v-2l-1-3v-44l-1-9-3 6-2 11-3 39-3 4-2-2-2-1-2 2v5h-2l-2 2-1-3v-16l2-11 2-4v-7h-2l-3-21-1 3h-2v8l-2-1-1-4-2 12h-1v-11l3-16 2-1 1-7 3-2 2 4 2-2 3 3 1 6 1 1 3 40 2-7 2-32 2-7 1-3 3-1 1-5h2l1 2h3v2h2v-3l6-1 4 2 1-5 6-11z"
            fill="#900D23"
          />
          <path
            transform="translate(795,778)"
            d="m0 0h1v36l2 19 5 19 6 16-1 2-10 2-2 1-8-2-1-2-3-1-1 4-1 2h-6l-8-5-4 1-2 1v-2h-3l-1-8h2l2-7 3-2h2l1 5h2v-3h2l1-20h1l1 10 2-19h1l1 19 2 13 1 1 1-9 1-37 1-13h1l1-10 4 2 2-11z"
            fill="#880A3D"
          />
          <path
            transform="translate(597,581)"
            d="m0 0h3l3 6 3-3 1 5 5 1 4 4 3 7 5 3 5 10 5 16v7l3 1 1 10-1-2-4 4 1 1 5-1-1 7 3 6v2l5 1 2 6-1 2h2v6h2l1-3 5 4h2l-1 4-2 4-4 3-2 11h-3l1-6 1-2h-2l-1-5-5-5-3-10-9-9-7-3 1-5 1-2h4v-5l-2-4-2-7 1-1v-8l-1 3h-2l-7-12-1-7h-6v6l-1 2h-2v2h-2l-1-3-2-16-1-7h-2z"
            fill="#D4120F"
          />
          <path
            transform="translate(751,863)"
            d="m0 0 1 2 6-1 1 5h2l-2 5 1 3h-17l-7 1 2-1-5-2 2 5h-2l-4 10-4 1v2l5-1-3 3-17 10-2 2-3-1 1-2h-11l-1-1-5 2v-2l-3 1-1-2-4 1-2-1 2-6-5 1-1 2v-3l13-10 8-2 5-6 5-3 2-2h3v-2l12-1 8-1 2 3h3l2-2-2-2 2-1h6 3v-2z"
            fill="#7D0A2D"
          />
          <path
            transform="translate(742,777)"
            d="m0 0 3 4 2-2 3 3 1 6 1 1 3 40 2-7h1v26l-3 4-2-2-2-1-2 2v5h-2l-2 2-1-3v-16l2-11 2-4v-7h-2l-3-21-1 3h-2v8l-2-1-1-4-2 12h-1v-11l3-16 2-1 1-7z"
            fill="#920D22"
          />
          <path
            transform="translate(795,778)"
            d="m0 0h1v36l2 19 1 6-3 1-4 8-5 2v8l-2 3-3-1 1-13 1-35 1-13h1l1-10 4 2 2-11z"
            fill="#660837"
          />
          <path
            transform="translate(731,787)"
            d="m0 0h1l1 8 1 1-1 11h-1l-1 41-2 1v-4h-2l-1 4-5-1-3 3-2-1v-15l1-5 1-19h2l1-5 2 4 3-16 4-1z"
            fill="#910D23"
          />
          <path
            transform="translate(794,758)"
            d="m0 0 1 3 2 1v2h2l-2 12-2 2-2-1-2 6-3-2-3 3-1 10-2 2-2-9-1 5h-2l1 3-2 1-1-2h-3l-2-6-1 4-2-8-2 4-2 2-1 7-1 1-1 7h-1v-15l2-7 1-3 3-1 1-5h2l1 2h3v2h2v-3l6-1 4 2 1-5 6-11z"
            fill="#A40C1B"
          />
          <path
            transform="translate(731,801)"
            d="m0 0h3l1 4 2-4h1l2 12-1 20-1 7-1-4h-2v8h2l2 4 1 11 3 2-3 1 3 2v3l-5 1v3l-3 3-4-2z"
            fill="#84093B"
          />
          <path
            transform="translate(793,777)"
            d="m0 0h2l-3 14h-3l-1-1-1 10h-1l-1 12-1 42-1 5-3-2-2-15-1-19 1-3 1-24 2-2 2 14v-17l2-10 3-1 3 2z"
            fill="#820A2A"
          />
          <path
            transform="translate(782,525)"
            d="m0 0 2 3 1 4 1 15 1 4 7 2 6 3-2 1 1 4-2 12-1 3h-2l-1 2-3-3-1-3-2-1v-4l-3 1v-24h-2l-1 9h-2l-2-16 3-1z"
            fill="#920D22"
          />
          <path
            transform="translate(515,373)"
            d="m0 0h5l2 8 5 6v7l-1 9 1 11v5l1 2-4 9-6 7-8 3h-8l-1-3 14-3 2-1 2-4 2-3 2-10-1-8-2-5 1-8-5-3-1-2 2-4 2 1-1-6-3-6z"
            fill="#D4120F"
          />
          <path
            transform="translate(714,807)"
            d="m0 0h1l1 7 1 36 1 8-2 4h-2v5l-4 2-3-5v-9l2-4 1-12-1-4 2-1v-16l1-7z"
            fill="#890A3D"
          />
          <path
            transform="translate(592,590)"
            d="m0 0h1l3 20h2l2 9-1 17h-3l-2 13 6-1 5 7-2 2 1 6-6-4-5-6-1-5z"
            fill="#D2120F"
          />
          <path
            transform="translate(475,331)"
            d="m0 0h20l4 1v2h-2v2l3 1-1 2 3-1v2h-4l1 3h-4v2l4 1 3 2-9-1-17-2-2-1v-2h-2v-2l5-2 1-3-3-2z"
            fill="#D5130F"
          />
          <path
            transform="translate(743,795)"
            d="m0 0h1l2 16v6h2l1 7-1 8-2-1-2 14h-1l-1-5-2-2-1 10-2 1v-5h-2v-8h2l1-5 1-18 1-14h2z"
            fill="#740A2F"
          />
          <path
            transform="translate(784,460)"
            d="m0 0 1 2h2v88l10-4 30-15 20-8 5-1-1 2-10 4-13 6-14 6 6-1h3v2h-4l-1 3-6 1h-3l-4-1v2l-8 3v6l-10-3-2-5-1-39z"
            fill="#820B3D"
          />
          <path
            transform="translate(726,883)"
            d="m0 0 5 2-2 5-4 1v2l5-1-3 3-17 10-2 2-3-1 1-2h-5l2-6 6-6 7-3 6-4z"
            fill="#730A30"
          />
          <path
            transform="translate(793,794)"
            d="m0 0h1l1 18 1 2 1 14-3 11h-2l-1-6-2 6-2-4-2-2v-17h1l1-9 2-2 2 6 1-14z"
            fill="#671046"
          />
          <path
            transform="translate(728,523)"
            d="m0 0h2l2 7 2-1v29h-3l-1-3-1 2h-2l-3-10v-6l1-2 2-15z"
            fill="#A50C1B"
          />
          <path
            transform="translate(742,777)"
            d="m0 0 3 4 2-2 3 3 1 6 1 1v10l-3-2-3-7-1 8-2-2-1 3h-2v8l-2-1-1-4-2 12h-1v-11l3-16 2-1 1-7z"
            fill="#A40C1B"
          />
          <path
            transform="translate(766,791)"
            d="m0 0h1l1 10v28l-1 13h-1l-1-5h-3v-29l1-7 2-1z"
            fill="#610B42"
          />
          <path
            transform="translate(795,778)"
            d="m0 0h1l-1 34h-1l-1-13-1 16-4-8-3-1v-7h1l1-10 4 2 2-11z"
            fill="#720A30"
          />
          <path
            transform="translate(974,397)"
            d="m0 0 2 2-14 12-20 16-4 3-2-1 3-4 3-1 2-4 2-3 5-3 3-1 1-3 8-6 7-4 2-2z"
            fill="#5C1B52"
          />
          <path
            transform="translate(755,785)"
            d="m0 0h1l1 17 1 3v17l-2 7-2 1-2-26 1-3z"
            fill="#C11110"
          />
          <path
            transform="translate(613,712)"
            d="m0 0h6l1 5-3 5-7 5-3-1v-11z"
            fill="#D5130F"
          />
          <path
            transform="translate(796,828)"
            d="m0 0h1l2 11-3 1-4 8-5 2v8l-2 3-3-1 1-13 2-3 3 1 1 1 2-4v-3h3z"
            fill="#740A31"
          />
          <path
            transform="translate(730,803)"
            d="m0 0h1v32l-3-4-3-7 1-16 3-1z"
            fill="#880A28"
          />
          <path
            transform="translate(384,326)"
            d="m0 0h17v1l-9 2-8 4-5 1-2 4h-2l-1 3h-2l2-7 5-6z"
            fill="#B91015"
          />
          <path
            transform="translate(764,832)"
            d="m0 0h1l4 16 1 3v6l-3 1v-6l-4 3v2l-3-1 2-14z"
            fill="#720930"
          />
          <path
            transform="translate(782,525)"
            d="m0 0 2 3 1 4v15l-1-3h-2l-1 9h-2l-2-16 3-1z"
            fill="#920D22"
          />
          <path
            transform="translate(784,460)"
            d="m0 0 1 2h2l-1 85h-1l-1-39z"
            fill="#850A38"
          />
          <path
            transform="translate(752,805)"
            d="m0 0h1l2 24 2-7h1v10l-2 10-2 1-2-6z"
            fill="#A50C1A"
          />
          <path
            transform="translate(1e3 374)"
            d="m0 0 2 1-11 11-11 9-3 3-3-1 2-1 1-3h2l2-4 5-5 4-3h2v-2l4-2 1-2z"
            fill="#500D5D"
          />
          <path
            transform="translate(743,797)"
            d="m0 0h1l2 14v6h2l1 7-1 8-4-2-1-9z"
            fill="#880A3B"
          />
          <path
            transform="translate(767,783)"
            d="m0 0 2 4-3 5-3 6-2 11-2 22h-1v-26h2v-7l2-7 1-3 2-1z"
            fill="#950D21"
          />
          <path
            transform="translate(766,791)"
            d="m0 0h1l1 10v28h-1l-1-21-1 9h-1l-1 20h-1v-29l1-7 2-1z"
            fill="#6F0A33"
          />
          <path
            transform="translate(596,648)"
            d="m0 0h4l5 7-2 2 1 6-6-4-5-6v-4z"
            fill="#CF1211"
          />
          <path
            transform="translate(795,840)"
            d="m0 0h1l-1 7-2 7-2 1-2 8-5 1v-3l2-3 1-8 5-2 2-5z"
            fill="#7A0741"
          />
          <path
            transform="translate(793,777)"
            d="m0 0h2l-3 14h-3-3l-2 3-1-3 2-10 3-1 3 2z"
            fill="#910D23"
          />
          <path
            transform="translate(780,794)"
            d="m0 0 2 4v16h-1l-1 16-2-1-1-6 1-3 1-24z"
            fill="#870A28"
          />
          <path
            transform="translate(739,786)"
            d="m0 0h1v12l-1 8-2-4-2 12h-1v-11l3-16z"
            fill="#A50C1B"
          />
          <path
            transform="translate(795,778)"
            d="m0 0h1l-1 34h-1l-1-21h-1v-7l2-5zm-8 11 5 2v3l-5-1z"
            fill="#7D0A35"
          />
          <path
            transform="translate(1188,976)"
            d="m0 0 3 4 4 14v15l-2-3-1-3-2-18z"
            fill="#442261"
          />
          <path
            transform="translate(993,970)"
            d="m0 0 3 1 4 4v2l3 1 4 6 4 4-1 3-5-5-11-12z"
            fill="#221B7E"
          />
          <path
            transform="translate(739,821)"
            d="m0 0h1v14h2v5l-2-2-1 10-2 1v-5h-2v-8h2l1-5z"
            fill="#7D0B2D"
          />
          <path
            transform="translate(755,785)"
            d="m0 0h1l1 17-1 13-2-2v-24z"
            fill="#D5130F"
          />
          <path
            transform="translate(774,707)"
            d="m0 0 2 2v10l4 1-2 5-3 1-2-5v-13z"
            fill="#D5130F"
          />
          <path
            transform="translate(776,823)"
            d="m0 0h1v15l-2 13h-1v-24z"
            fill="#A30C1B"
          />
          <path
            transform="translate(786,541)"
            d="m0 0h1v9l10-4 4-1-4 4v6l-10-3-1-1z"
            fill="#7F0B3B"
          />
          <path
            transform="translate(592,730)"
            d="m0 0 2 3 1 13-1 7-1 5h-1z"
            fill="#D5130F"
          />
          <path
            transform="translate(756,718)"
            d="m0 0 4 3v2l2 1h-2l-1 2-4-1-7 3-1-3 5-3z"
            fill="#D5130F"
          />
          <path
            transform="translate(746,828)"
            d="m0 0 2 4 1 5-1 10h-1l-1 5h-1v-21z"
            fill="#A00C1D"
          />
          <path
            transform="translate(742,785)"
            d="m0 0h1l1 10-2 4h-2v8h-1l1-21z"
            fill="#8E0C25"
          />
          <path
            transform="translate(681,613)"
            d="m0 0 3 1v3h-2l1 4-4 5-3-3 3-8h2z"
            fill="#D5130F"
          />
          <path
            transform="translate(1022 1e3)"
            d="m0 0 5 2 5 5 4 6v2l-4-2-7-8-3-3z"
            fill="#251B7B"
          />
          <path
            transform="translate(909,449)"
            d="m0 0h3l-1 3-5 3h-9v-3l10-2z"
            fill="#5C1B52"
          />
          <path
            transform="translate(932,432)"
            d="m0 0h2v2l-14 11-3-1 5-6 4-1z"
            fill="#5F1A51"
          />
          <path
            transform="translate(784,460)"
            d="m0 0 1 2h2l-1 24h-1z"
            fill="#7C0B36"
          />
          <path
            transform="translate(785,816)"
            d="m0 0 3 2v12l-3 3z"
            fill="#6A1046"
          />
          <path
            transform="translate(513,356)"
            d="m0 0h2l3 11h-3l-3-5z"
            fill="#D4120F"
          />
          <path
            transform="translate(757,871)"
            d="m0 0 3 2v4h-12l3-3 5-2z"
            fill="#730A30"
          />
          <path
            transform="translate(746,797)"
            d="m0 0 1 3 2 1v10l-3-1z"
            fill="#880A27"
          />
          <path
            transform="translate(821,538)"
            d="m0 0 2 1v2h-4l-1 3-6 1h-3l1-2h3v-2l7-2z"
            fill="#890A3D"
          />
          <path
            transform="translate(746,817)"
            d="m0 0h2l1 7-1 8-2-4z"
            fill="#810A32"
          />
          <path
            transform="translate(767,845)"
            d="m0 0 3 4v8l-3 1z"
            fill="#7D0A2D"
          />
          <path
            transform="translate(762,846)"
            d="m0 0 1 4 3-1-1 4-2 2v2l-3-1z"
            fill="#7D0A2D"
          />
          <path
            transform="translate(782,525)"
            d="m0 0 2 3 1 5-1 3-4-1z"
            fill="#A50C1B"
          />
        </svg>
        </div>
        <div class="scoreboard">
            <div class="score-container">
                <div class="player-name">PLAYER 1</div>
                <div class="score">000</div>
            </div>
            <div class="score-container">
                <div class="player-name">PLAYER 2</div>
                <div class="score">000</div>
            </div>
        </div>
        <button class="reset-btn">RESET</button>
    </div>
    <div class="spaceship">🚀</div>
    <script>
        // Create stars
        for (let i = 0; i < 100; i++) {
        let star = document.createElement("div");
        star.className = "stars";
            star.style.left = `${Math.random() * 100}%`;
            star.style.top = `${Math.random() * 100}%`;
            star.style.animationDuration = `${Math.random() * 3 + 1}s`;
        star.style.animationName = "twinkle";
        star.style.animationIterationCount = "infinite";
            document.body.appendChild(star);
        }

        function connectWebSocket() {
        // Get the current hostname (IP address or domain)
        const wsHost = window.location.hostname;
        var ws = new WebSocket(`ws://${wsHost}:8000/ws`);
            
        ws.onopen = function () {
                console.log("WebSocket connected");
            };

        ws.onclose = function () {
                console.log("WebSocket disconnected, reconnecting...");
                setTimeout(connectWebSocket, 1000);
            };
            
        ws.onmessage = function (event) {
            if (event.data === "reset_acknowledged") {
                console.log("Game reset initiated");
                return;
            }

            try {
                const scores = JSON.parse(event.data);
                // Update player 1 score
                if (scores.player_1) {
                    document.querySelector(
                        ".score-container:nth-child(1) .score"
                    ).innerText = String(scores.player_1).padStart(3, "0");
                }
                // Update player 2 score
                if (scores.player_2) {
                    document.querySelector(
                        ".score-container:nth-child(2) .score"
                    ).innerText = String(scores.player_2).padStart(3, "0");
                }
            } catch (e) {
                console.error("Error updating scores:", e);
            }
        };
            
            // Add reset button functionality
        document
          .querySelector(".reset-btn")
          .addEventListener("click", function () {
            ws.send("reset");
            });

            return ws;
        }

        // Start WebSocket connection
        connectWebSocket();
    </script>
</body>
</html>

"""

@app.get("/")
async def get():
    return HTMLResponse(html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)