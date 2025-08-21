"""Whisper transcription server for multi-worker GPU sharing."""

import os
import time
import queue
from typing import Optional, Tuple, Dict, Any
from multiprocessing import Process, Queue, Event
from pathlib import Path

class WhisperServer:
    """Dedicated server process for Whisper transcription on GPU."""
    
    def __init__(self, request_queue: Queue, response_queue: Queue, 
                 shutdown_event: Event, device_config: Dict[str, Any]):
        """Initialize Whisper server.
        
        Args:
            request_queue: Queue for receiving transcription requests
            response_queue: Queue for sending transcription results
            shutdown_event: Event to signal shutdown
            device_config: Configuration for device and model
        """
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.shutdown_event = shutdown_event
        self.device_config = device_config
        self.model = None
        
    def run(self):
        """Main server loop."""
        print(f"[Whisper Server] Starting on {self.device_config.get('device', 'cpu').upper()}...")
        
        # Get device configuration
        device = self.device_config.get('device', 'cuda')
        if device == 'cuda':
            print(f"[Whisper Server] Using CUDA device")
        
        # Load model once on GPU
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                model_size_or_path=self.device_config.get('model_size', 'small.en'),
                device=device,
                compute_type=self.device_config.get('compute_type', 'float16'),
                device_index=0  # Explicitly use first GPU
            )
            print(f"[Whisper Server] ✓ Model loaded on {device.upper()}")
        except Exception as e:
            print(f"[Whisper Server] FATAL: Failed to load model on {device.upper()}: {e}")
            if device == 'cuda':
                print("[Whisper Server] CUDA initialization failed. This usually means:")
                print("  1. Another process is using the GPU")
                print("  2. CUDA is not properly installed")
                print("  3. GPU memory is full")
                print("  Try: nvidia-smi to check GPU status")
            import sys
            sys.exit(1)  # Exit with error code
        
        # Process requests
        while not self.shutdown_event.is_set():
            try:
                # Get request with timeout
                request = self.request_queue.get(timeout=0.5)
                
                if request is None:  # Shutdown signal
                    break
                    
                # Extract request data
                request_id = request.get('id')
                audio_path = request.get('audio_path')
                worker_id = request.get('worker_id', -1)
                
                if not audio_path or not os.path.exists(audio_path):
                    self.response_queue.put({
                        'id': request_id,
                        'success': False,
                        'error': 'Audio file not found',
                        'transcript': ''
                    })
                    continue
                
                # Perform transcription
                print(f"[Whisper Server] Transcribing for Worker {worker_id}: {Path(audio_path).name}")
                
                try:
                    segments, _ = self.model.transcribe(
                        audio_path,
                        beam_size=5,
                        best_of=5,
                        temperature=0,
                        condition_on_previous_text=False
                    )
                    transcript = " ".join([segment.text.strip() for segment in segments])
                    
                    # Send response
                    self.response_queue.put({
                        'id': request_id,
                        'success': True,
                        'transcript': transcript,
                        'worker_id': worker_id
                    })
                    
                except Exception as e:
                    print(f"[Whisper Server] Transcription error: {e}")
                    self.response_queue.put({
                        'id': request_id,
                        'success': False,
                        'error': str(e),
                        'transcript': ''
                    })
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Whisper Server] Error processing request: {e}")
                
        print("[Whisper Server] Shutting down...")
        if self.model:
            del self.model
            
            
class WhisperClient:
    """Client for workers to request transcriptions from Whisper server."""
    
    def __init__(self, request_queue: Queue, response_queue: Queue, worker_id: int):
        """Initialize Whisper client.
        
        Args:
            request_queue: Queue for sending requests to server
            response_queue: Queue for receiving responses from server
            worker_id: ID of the worker using this client
        """
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.worker_id = worker_id
        self._request_counter = 0
        
    def transcribe(self, audio_path: str) -> Optional[str]:
        """Request transcription from server.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcript text or None if failed
        """
        # Generate unique request ID
        self._request_counter += 1
        request_id = f"worker_{self.worker_id}_req_{self._request_counter}"
        
        # Send request
        self.request_queue.put({
            'id': request_id,
            'audio_path': audio_path,
            'worker_id': self.worker_id
        })
        
        # Wait for response (no timeout - wait as long as needed)
        while True:
            try:
                # Check response queue
                response = self.response_queue.get(timeout=1.0)
                
                # Check if this is our response
                if response.get('id') == request_id:
                    if response.get('success'):
                        return response.get('transcript', '')
                    else:
                        print(f"[Worker {self.worker_id}] Transcription failed: {response.get('error')}")
                        return None
                else:
                    # Not our response, put it back
                    self.response_queue.put(response)
                    time.sleep(0.01)  # Brief pause before checking again
                    
            except queue.Empty:
                continue  # Keep waiting


def start_whisper_server(request_queue: Queue, response_queue: Queue, 
                        shutdown_event: Event, device_config: Dict[str, Any]) -> Process:
    """Start Whisper server in a separate process.
    
    Args:
        request_queue: Queue for receiving requests
        response_queue: Queue for sending responses
        shutdown_event: Event to signal shutdown (not used directly in subprocess)
        device_config: Device configuration
        
    Returns:
        Process object for the server
    """
    def server_worker():
        # Create a local event for this process
        import multiprocessing
        local_shutdown_event = multiprocessing.Event()
        server = WhisperServer(request_queue, response_queue, local_shutdown_event, device_config)
        server.run()
    
    process = Process(target=server_worker, daemon=False)
    process.start()
    return process