#!/usr/bin/env python3
"""
TensorRT Model Optimization for Dealereye
Exports YOLOv8 models to TensorRT format for Jetson GPU acceleration
"""

import argparse
import os
from ultralytics import YOLO

def export_to_tensorrt(model_path, imgsz=640, half=True, workspace=4):
    """
    Export YOLOv8 model to TensorRT format

    Args:
        model_path: Path to YOLOv8 .pt model
        imgsz: Input image size (default: 640)
        half: Use FP16 precision (default: True, recommended for Jetson)
        workspace: Max workspace size in GB (default: 4)

    Returns:
        Path to exported .engine file
    """
    print("=" * 60)
    print("TensorRT Model Export for Jetson")
    print("=" * 60)

    # Load model
    print(f"\n1. Loading model: {model_path}")
    model = YOLO(model_path)

    # Get model info
    print(f"   Model type: {model.model_name if hasattr(model, 'model_name') else 'YOLOv8'}")

    # Export to TensorRT
    print(f"\n2. Exporting to TensorRT...")
    print(f"   - Image size: {imgsz}")
    print(f"   - Precision: {'FP16' if half else 'FP32'}")
    print(f"   - Workspace: {workspace}GB")
    print(f"\n   This may take several minutes...\n")

    try:
        # Export with TensorRT settings optimized for Jetson
        export_path = model.export(
            format='engine',           # TensorRT format
            imgsz=imgsz,              # Input size
            half=half,                # FP16 precision
            workspace=workspace,       # Workspace in GB
            verbose=True,             # Show export progress
            device=0                   # Use GPU 0
        )

        print(f"\n✅ Export complete!")
        print(f"   TensorRT engine: {export_path}")

        # Get file size
        if os.path.exists(export_path):
            size_mb = os.path.getsize(export_path) / (1024 * 1024)
            print(f"   File size: {size_mb:.1f} MB")

        return export_path

    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        print("\nTroubleshooting:")
        print("  - Ensure you're running on Jetson with CUDA/TensorRT installed")
        print("  - Check available GPU memory")
        print("  - Try reducing workspace size or using FP32 (half=False)")
        return None

def benchmark_model(model_path, imgsz=640, iterations=100):
    """
    Benchmark inference speed

    Args:
        model_path: Path to model (.pt or .engine)
        imgsz: Input image size
        iterations: Number of warmup + benchmark iterations
    """
    print("\n" + "=" * 60)
    print("Benchmarking Model Performance")
    print("=" * 60)

    model = YOLO(model_path)

    # Run benchmark
    print(f"\nRunning {iterations} iterations at {imgsz}x{imgsz}...")
    results = model.val(
        data='coco8.yaml',  # Small validation set
        imgsz=imgsz,
        batch=1,
        verbose=False
    )

    print(f"\n📊 Results:")
    print(f"   Speed: {results.speed['inference']:.1f}ms pre-process + "
          f"{results.speed['inference']:.1f}ms inference + "
          f"{results.speed['postprocess']:.1f}ms post-process")
    print(f"   Total: {sum(results.speed.values()):.1f}ms per image")
    print(f"   FPS: {1000 / sum(results.speed.values()):.1f}")

def compare_models(pt_path, engine_path, imgsz=640):
    """
    Compare PyTorch vs TensorRT performance

    Args:
        pt_path: Path to .pt model
        engine_path: Path to .engine model
        imgsz: Input size
    """
    print("\n" + "=" * 60)
    print("PyTorch vs TensorRT Comparison")
    print("=" * 60)

    print("\n1. Testing PyTorch model...")
    benchmark_model(pt_path, imgsz)

    print("\n2. Testing TensorRT model...")
    benchmark_model(engine_path, imgsz)

def main():
    parser = argparse.ArgumentParser(description='Optimize YOLOv8 for Jetson with TensorRT')
    parser.add_argument('--model', type=str, default='yolov8n.pt',
                        help='YOLOv8 model to optimize (default: yolov8n.pt)')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='Input image size (default: 640)')
    parser.add_argument('--half', action='store_true', default=True,
                        help='Use FP16 precision (default: True)')
    parser.add_argument('--workspace', type=int, default=4,
                        help='TensorRT workspace in GB (default: 4)')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run benchmark after export')
    parser.add_argument('--compare', action='store_true',
                        help='Compare PyTorch vs TensorRT performance')

    args = parser.parse_args()

    # Check if model exists, download if needed
    if not os.path.exists(args.model):
        print(f"Model {args.model} not found, downloading...")
        model = YOLO(args.model)  # Auto-downloads

    # Export to TensorRT
    engine_path = export_to_tensorrt(
        args.model,
        imgsz=args.imgsz,
        half=args.half,
        workspace=args.workspace
    )

    if not engine_path:
        return 1

    # Benchmark if requested
    if args.benchmark:
        benchmark_model(engine_path, args.imgsz)

    # Compare if requested
    if args.compare:
        compare_models(args.model, engine_path, args.imgsz)

    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print(f"\nTo use the optimized model, update app.py:")
    print(f'  detector = Detector(model_path="{os.path.basename(engine_path)}")')
    print(f"\nOr set as environment variable:")
    print(f'  export MODEL_PATH="{engine_path}"')
    print("=" * 60)

    return 0

if __name__ == "__main__":
    exit(main())
