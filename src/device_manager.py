"""Centralized device detection and management for GPU/CPU operations."""

import torch
import subprocess
from typing import Tuple, Optional

class DeviceManager:
    """Manages device selection for ML operations (CUDA, MPS, CPU)."""
    
    # Cache device detection results
    _cached_device: Optional[str] = None
    _device_checked: bool = False
    
    @classmethod
    def get_best_device(cls, force_cpu: bool = False) -> str:
        """
        Get the best available device for ML operations.
        
        Priority:
        1. CUDA (NVIDIA GPU)
        2. MPS (Apple Silicon GPU)
        3. CPU
        
        Args:
            force_cpu: Force CPU usage even if GPU is available
            
        Returns:
            Device string: 'cuda', 'mps', or 'cpu'
        """
        if force_cpu:
            return 'cpu'
        
        # Use cached result if available
        if cls._device_checked and cls._cached_device:
            return cls._cached_device
        
        # Check for CUDA (NVIDIA GPU)
        if torch.cuda.is_available():
            cls._cached_device = 'cuda'
            cls._device_checked = True
            print("✓ NVIDIA GPU detected (CUDA)")
            return 'cuda'
        
        # Check for MPS (Apple Silicon GPU)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            cls._cached_device = 'mps'
            cls._device_checked = True
            print("✓ Apple Silicon GPU detected (MPS)")
            return 'mps'
        
        # Fallback to CPU
        cls._cached_device = 'cpu'
        cls._device_checked = True
        print("ℹ Using CPU (no GPU detected)")
        return 'cpu'
    
    @staticmethod
    def get_compute_type(device: str) -> str:
        """
        Get optimal compute type for the device.
        
        Args:
            device: Device string ('cuda', 'mps', 'cpu')
            
        Returns:
            Compute type for faster-whisper
        """
        if device == 'cuda':
            return 'float16'  # Best for NVIDIA GPUs
        elif device == 'mps':
            # MPS may have issues with float16, use float32 for stability
            return 'float32'
        else:
            return 'int8'  # Best for CPU (quantized)
    
    @staticmethod
    def get_device_info() -> dict:
        """
        Get detailed device information.
        
        Returns:
            Dictionary with device capabilities
        """
        info = {
            'cuda_available': torch.cuda.is_available(),
            'mps_available': hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(),
            'cuda_device_count': torch.cuda.device_count() if torch.cuda.is_available() else 0,
            'cuda_device_name': None,
            'cpu_count': torch.get_num_threads()
        }
        
        if info['cuda_available'] and info['cuda_device_count'] > 0:
            info['cuda_device_name'] = torch.cuda.get_device_name(0)
        
        return info
    
    @staticmethod
    def check_nvidia_smi() -> bool:
        """
        Check if nvidia-smi is available (for CUDA verification).
        
        Returns:
            True if nvidia-smi command succeeds
        """
        try:
            result = subprocess.run(
                ['nvidia-smi'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @classmethod
    def get_whisper_device_config(cls, force_cpu: bool = False) -> Tuple[str, str]:
        """
        Get device and compute type configuration for Whisper.
        
        Args:
            force_cpu: Force CPU usage
            
        Returns:
            Tuple of (device, compute_type)
        """
        device = cls.get_best_device(force_cpu)
        compute_type = cls.get_compute_type(device)
        return device, compute_type
    
    @classmethod
    def print_device_warning(cls, num_workers: int, device: Optional[str] = None):
        """
        Print performance warning if using multiple workers with CPU.
        
        Args:
            num_workers: Number of worker processes
            device: Device being used (will auto-detect if not provided)
        """
        if device is None:
            device = cls.get_best_device()
        
        if device == 'cpu' and num_workers > 1:
            print(f"\n⚠️  Performance Note: Using {num_workers} workers with CPU transcription.")
            print("   Consider reducing workers or using a GPU for better performance.\n")
        elif device in ['cuda', 'mps'] and num_workers > 1:
            print(f"\n✓ Using {num_workers} workers with {device.upper()} acceleration.\n")