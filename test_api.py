#!/usr/bin/env python3
"""
Test script for Dealereye API
Tests camera management, detection, and recording functionality
"""

import requests
import time
import json

BASE_URL = "http://localhost:8080"

def print_response(response):
    """Pretty print API response"""
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print("-" * 50)

def test_system_status():
    """Test system status endpoint"""
    print("\n=== Testing System Status ===")
    response = requests.get(f"{BASE_URL}/")
    print_response(response)

def test_add_camera(camera_id, stream_url):
    """Test adding a camera"""
    print(f"\n=== Adding Camera: {camera_id} ===")
    response = requests.post(
        f"{BASE_URL}/cameras",
        json={
            "camera_id": camera_id,
            "stream_url": stream_url
        }
    )
    print_response(response)
    return response.status_code == 200

def test_list_cameras():
    """Test listing all cameras"""
    print("\n=== Listing Cameras ===")
    response = requests.get(f"{BASE_URL}/cameras")
    print_response(response)

def test_start_camera(camera_id):
    """Test starting a camera"""
    print(f"\n=== Starting Camera: {camera_id} ===")
    response = requests.post(f"{BASE_URL}/cameras/{camera_id}/start")
    print_response(response)
    return response.status_code == 200

def test_camera_stats(camera_id):
    """Test getting camera statistics"""
    print(f"\n=== Camera Stats: {camera_id} ===")
    response = requests.get(f"{BASE_URL}/cameras/{camera_id}/stats")
    print_response(response)

def test_camera_detections(camera_id):
    """Test getting detection results"""
    print(f"\n=== Camera Detections: {camera_id} ===")
    response = requests.get(f"{BASE_URL}/cameras/{camera_id}/detections")
    print_response(response)

def test_snapshot(camera_id, save_path="test_snapshot.jpg"):
    """Test getting a snapshot"""
    print(f"\n=== Getting Snapshot: {camera_id} ===")
    response = requests.get(f"{BASE_URL}/cameras/{camera_id}/snapshot")

    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Snapshot saved to {save_path}")
        print(f"File size: {len(response.content)} bytes")
    else:
        print(f"Failed: {response.status_code}")
        print(response.text)
    print("-" * 50)

def test_record_clip(camera_id, duration=5):
    """Test recording a clip"""
    print(f"\n=== Recording {duration}s Clip: {camera_id} ===")
    response = requests.post(
        f"{BASE_URL}/cameras/{camera_id}/record",
        json={"duration": duration}
    )
    print_response(response)

def test_stop_camera(camera_id):
    """Test stopping a camera"""
    print(f"\n=== Stopping Camera: {camera_id} ===")
    response = requests.post(f"{BASE_URL}/cameras/{camera_id}/stop")
    print_response(response)

def test_remove_camera(camera_id):
    """Test removing a camera"""
    print(f"\n=== Removing Camera: {camera_id} ===")
    response = requests.delete(f"{BASE_URL}/cameras/{camera_id}")
    print_response(response)

def main():
    """Run all tests"""
    print("=" * 50)
    print("Dealereye API Test Suite")
    print("=" * 50)

    # Test system status
    test_system_status()

    # Get camera details from user
    print("\n" + "=" * 50)
    print("Camera Configuration")
    print("=" * 50)
    print("\nOptions:")
    print("1. Test with RTSP camera")
    print("2. Test with video file")
    print("3. Skip camera tests")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        camera_id = input("Enter camera ID (e.g., 'front_gate'): ").strip()
        stream_url = input("Enter RTSP URL: ").strip()
    elif choice == "2":
        camera_id = input("Enter camera ID (e.g., 'test_cam'): ").strip()
        stream_url = input("Enter video file path: ").strip()
    else:
        print("\nSkipping camera tests")
        return

    # Add camera
    if not test_add_camera(camera_id, stream_url):
        print("\n❌ Failed to add camera, stopping tests")
        return

    # List cameras
    test_list_cameras()

    # Start camera
    if not test_start_camera(camera_id):
        print("\n❌ Failed to start camera, stopping tests")
        return

    # Wait for camera to initialize
    print("\nWaiting 5 seconds for camera to initialize...")
    time.sleep(5)

    # Check stats
    test_camera_stats(camera_id)

    # Wait for detections
    print("\nWaiting 10 seconds for detections...")
    time.sleep(10)

    # Check detections
    test_camera_detections(camera_id)

    # Get snapshot
    test_snapshot(camera_id)

    # Record clip
    record = input("\nRecord a 5-second clip? (y/n): ").strip().lower()
    if record == 'y':
        test_record_clip(camera_id, duration=5)
        print("\nWaiting for recording to complete...")
        time.sleep(6)

    # Cleanup
    cleanup = input("\nStop and remove camera? (y/n): ").strip().lower()
    if cleanup == 'y':
        test_stop_camera(camera_id)
        test_remove_camera(camera_id)

    print("\n" + "=" * 50)
    print("✅ Test suite completed!")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
