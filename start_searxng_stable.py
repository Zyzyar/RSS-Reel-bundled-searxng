#!/usr/bin/env python3
"""
Stable SearxNG launcher with auto-restart and health monitoring
Keeps SearxNG running non-stop until manually stopped
"""

import os
import sys
import subprocess
import time
import threading
import signal
import logging
import atexit
import glob
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None
from pathlib import Path
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [SEARXNG-STABLE] - %(message)s',
    handlers=[
        logging.FileHandler('searxng_stable.log'),
        logging.StreamHandler()
    ]
)

class StableSearxNG:
    def __init__(self):
        self.searxng_dir = Path(__file__).parent
        self.python_exe = self.searxng_dir / "python" / "python.exe"
        self.webapp_py = self.searxng_dir / "python" / "Lib" / "site-packages" / "searx" / "webapp.py"
        self.config_dir = self.searxng_dir / "config"
        
        self.process = None
        self.running = False
        self.health_check_interval = 30  # seconds
        self.restart_delay = 5  # seconds after crash
        self.port = 5001
        self.base_url = f"http://127.0.0.1:{self.port}"
        
        # Environment for SearxNG
        self.env = os.environ.copy()
        self.env['SEARXNG_SETTINGS_PATH'] = str(self.config_dir / "settings.yml")
        self.env['SEARXNG_PORT'] = str(self.port)
        self.env['SEARXNG_BIND_ADDRESS'] = '127.0.0.1'
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.env['PYTHONUNBUFFERED'] = '1'
        
        # No timeout for workers - run indefinitely
        self.env['SEARXNG_WORKER_TIMEOUT'] = '0'  
        
        # Register cleanup function to remove cache on exit
        atexit.register(self._cleanup_cache)
        signal.signal(signal.SIGBREAK, lambda s, f: self._cleanup_cache())
        signal.signal(signal.SIGINT, lambda s, f: self._cleanup_cache())
        signal.signal(signal.SIGTERM, lambda s, f: self._cleanup_cache())

    def _log_active_engines(self):
        """Log which engines are enabled (disabled != true) and where settings are read from."""
        settings_file = self.config_dir / "settings.yml"
        logging.info(f"[CFG] Using settings file: {settings_file}")
        if not settings_file.exists():
            logging.warning("[CFG] settings.yml not found; cannot list engines")
            return
        if yaml is None:
            logging.warning("[CFG] PyYAML not available; skipping engine listing")
            return
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            engines = data.get("engines", []) if isinstance(data, dict) else []
            active = []
            for eng in engines:
                if not isinstance(eng, dict):
                    continue
                if eng.get("disabled", False):
                    continue
                name = eng.get("name", "<unknown>")
                backend = eng.get("engine", "<engine>")
                active.append(f"{name} ({backend})")
            logging.info(f"[CFG] Active engines: {len(active)}")
            for entry in active:
                logging.info(f"[CFG]   - {entry}")
        except Exception as e:
            logging.warning(f"[CFG] Could not read engines from settings.yml: {e}")

    def start(self):
        """Start SearxNG process"""
        if self.process and self.process.poll() is None:
            logging.info("SearxNG is already running")
            return
            
        try:
            logging.info(f"Starting SearxNG (waitress) on port {self.port}...")
            self._log_active_engines()
            
            # Prefer waitress (installed) for production-like serving on Windows
            cmd = [
                str(self.python_exe),
                "-m",
                "waitress",
                "--host", "127.0.0.1",
                "--port", str(self.port),
                "--threads", "10",
                "searx.webapp:app"
            ]
            
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.searxng_dir),
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            self.running = True
            
            # Wait for startup
            time.sleep(3)
            
            # Start log reader thread
            threading.Thread(target=self._read_output, daemon=True).start()
            
            # Verify it started
            if self.health_check():
                logging.info(f" SearxNG started successfully on {self.base_url}")
            else:
                logging.warning(" SearxNG started but not responding yet")
                
        except Exception as e:
            logging.error(f"Failed to start SearxNG: {e}")
            self.running = False
            
    def _read_output(self):
        """Read process output in background"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    # Log important lines only
                    if any(keyword in line.lower() for keyword in ['error', 'warning', 'started', 'listening']):
                        logging.info(f"[SEARXNG-OUTPUT] {line.strip()}")
        except:
            pass
            
    def _cleanup_cache(self):
        """Remove SearxNG cache files on shutdown"""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            cache_pattern = os.path.join(temp_dir, "sxng_cache_*.db")
            cache_files = glob.glob(cache_pattern)
            
            logging.info(f"[CACHE] Starting cleanup in: {temp_dir}")
            logging.info(f"[CACHE] Found {len(cache_files)} cache files")
            
            removed_count = 0
            for cache_file in cache_files:
                try:
                    file_size = os.path.getsize(cache_file) if os.path.exists(cache_file) else 0
                    os.remove(cache_file)
                    logging.info(f"[CACHE] ✓ Removed: {os.path.basename(cache_file)} ({file_size} bytes)")
                    removed_count += 1
                except Exception as e:
                    logging.warning(f"[CACHE] ✗ Could not remove {cache_file}: {e}")
            
            logging.info(f"[CACHE] Cleanup completed: {removed_count}/{len(cache_files)} files removed")
            
        except Exception as e:
            logging.error(f"[CACHE] Cache cleanup failed: {e}")
            import traceback
            logging.error(f"[CACHE] Traceback: {traceback.format_exc()}")
    
    def stop(self):
        """Stop SearxNG process"""
        self.running = False
        
        if self.process:
            try:
                logging.info("Stopping SearxNG...")
                self.process.terminate()
                time.sleep(2)
                
                if self.process.poll() is None:
                    self.process.kill()
                    
                self.process = None
                logging.info(" SearxNG stopped")
                
            except Exception as e:
                logging.error(f"Error stopping SearxNG: {e}")
        
        # Always cleanup cache on stop
        self._cleanup_cache()
                
    def restart(self):
        """Restart SearxNG"""
        logging.info("Restarting SearxNG...")
        self.stop()
        time.sleep(self.restart_delay)
        self.start()
        
    def health_check(self):
        """Check if SearxNG is responding"""
        if HAS_REQUESTS:
            try:
                response = requests.get(
                    f"{self.base_url}/healthz",
                    timeout=5
                )
                return response.status_code == 200
            except:
                # Try alternative endpoint
                try:
                    response = requests.get(
                        f"{self.base_url}/search?q=test&format=json",
                        timeout=5
                    )
                    return response.status_code in [200, 202]
                except:
                    return False
        else:
            # Use urllib as fallback
            try:
                req = urllib.request.Request(f"{self.base_url}/healthz")
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except:
                # Try alternative endpoint
                try:
                    req = urllib.request.Request(f"{self.base_url}/search?q=test&format=json")
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return response.status in [200, 202]
                except:
                    return False
                
    def monitor_loop(self):
        """Main monitoring loop - keeps SearxNG running forever"""
        logging.info("Starting SearxNG monitor loop (non-stop mode)")
        
        # Initial start
        self.start()
        
        while self.running:
            try:
                time.sleep(self.health_check_interval)
                
                # Check process status
                if self.process and self.process.poll() is not None:
                    logging.warning(f" SearxNG process died (exit code: {self.process.poll()})")
                    self.restart()
                    continue
                    
                # Health check
                if not self.health_check():
                    logging.warning(" SearxNG not responding, restarting...")
                    self.restart()
                    continue
                    
                logging.debug(" SearxNG is healthy")
                    
            except KeyboardInterrupt:
                logging.info("Received shutdown signal")
                self.running = False
                break
            except Exception as e:
                logging.error(f"Monitor error: {e}")
                time.sleep(10)
                
        # Clean shutdown
        self.stop()
        logging.info("SearxNG monitor stopped")
        
def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logging.info(f"Received signal {signum}, shutting down...")
    # Cleanup cache before exit
    try:
        import tempfile
        import glob
        temp_dir = tempfile.gettempdir()
        cache_files = glob.glob(os.path.join(temp_dir, "sxng_cache_*.db"))
        for cache_file in cache_files:
            try:
                os.remove(cache_file)
                logging.info(f"[CACHE] Signal cleanup: Removed {cache_file}")
            except:
                pass
    except:
        pass
    sys.exit(0)

def main():
    """Main entry point"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run stable SearxNG
    searxng = StableSearxNG()
    
    try:
        searxng.monitor_loop()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        searxng.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
