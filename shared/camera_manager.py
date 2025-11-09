"""
Camera configuration management.
Handles storing and retrieving camera configurations.
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from uuid import UUID, uuid4


class CameraManager:
    """Manages camera configurations stored in JSON file."""

    def __init__(self, config_path: str = "/opt/dealereye/config/cameras.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize with empty list if file doesn't exist
        if not self.config_path.exists():
            self._save_cameras([])

    def _load_cameras(self) -> List[Dict]:
        """Load cameras from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_cameras(self, cameras: List[Dict]):
        """Save cameras to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(cameras, f, indent=2)

    def list_cameras(self) -> List[Dict]:
        """Get all cameras."""
        return self._load_cameras()

    def get_camera(self, camera_id: str) -> Optional[Dict]:
        """Get a specific camera by ID."""
        cameras = self._load_cameras()
        for camera in cameras:
            if camera.get('id') == camera_id:
                return camera
        return None

    def add_camera(self, name: str, rtsp_url: str) -> Dict:
        """Add a new camera."""
        cameras = self._load_cameras()

        # Always auto-generate UUID for new cameras
        camera_id = str(uuid4())

        camera = {
            "id": camera_id,
            "name": name,
            "rtsp_url": rtsp_url,
            "enabled": True
        }

        cameras.append(camera)
        self._save_cameras(cameras)
        return camera

    def update_camera(self, camera_id: str, **kwargs) -> Optional[Dict]:
        """Update camera configuration."""
        cameras = self._load_cameras()

        for i, camera in enumerate(cameras):
            if camera.get('id') == camera_id:
                # Update fields
                if 'name' in kwargs:
                    camera['name'] = kwargs['name']
                if 'rtsp_url' in kwargs:
                    camera['rtsp_url'] = kwargs['rtsp_url']
                if 'enabled' in kwargs:
                    camera['enabled'] = kwargs['enabled']

                cameras[i] = camera
                self._save_cameras(cameras)
                return camera

        return None

    def delete_camera(self, camera_id: str) -> bool:
        """Delete a camera."""
        cameras = self._load_cameras()
        original_count = len(cameras)

        cameras = [c for c in cameras if c.get('id') != camera_id]

        if len(cameras) < original_count:
            self._save_cameras(cameras)
            return True

        return False
