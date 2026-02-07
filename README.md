# OrbitalViz - PySCF MCSCF Visualization

A high-performance web application for visualizing PySCF MCSCF natural orbitals using Svelte, FastAPI, and Three.js. Designed for deployment on NRP Nautilus Kubernetes clusters.

## Features

- **Backend (FastAPI)**:
  - Streams raw Float32 binary buffers (no .cube files)
  - Evaluates Natural Orbitals on 3D grids with 3Å margins using `mol.eval_gto`
  - Efficient binary blob transfer via octet-stream
  - CORS-enabled API for decoupled frontend/backend

- **Frontend (Svelte + Threlte)**:
  - Real-time 3D orbital visualization with Three.js
  - Marching Cubes algorithm in Web Worker for 60fps rendering
  - Interactive isovalue sliders
  - Mobile-friendly touch controls
  - Orbital Controls for pan, zoom, and rotation

- **Architecture**:
  - Decoupled Kubernetes pods
  - Binary blob transfer for performance
  - Scalable microservices design

## Local Development

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Docker Build

### Build Backend

```bash
cd backend
docker build -t orbitalviz-backend:latest .
```

### Build Frontend

```bash
cd frontend
docker build -t orbitalviz-frontend:latest .
```

## Kubernetes Deployment

Deploy to NRP Nautilus or any Kubernetes cluster:

```bash
# Apply backend deployment
kubectl apply -f k8s/backend-deployment.yaml

# Apply frontend deployment
kubectl apply -f k8s/frontend-deployment.yaml

# Check pod status
kubectl get pods

# Check services
kubectl get services
```

## API Endpoints

- `GET /` - API health check
- `GET /api/molecule/info` - Get molecule information and number of orbitals
- `GET /api/orbital/{orbital_index}?grid_size={size}&margin={margin}` - Stream orbital data as Float32 binary buffer

### Binary Data Format

The orbital data endpoint returns:
- **Header** (36 bytes):
  - 3 integers (12 bytes): Grid dimensions (x, y, z)
  - 6 floats (24 bytes): Bounding box min/max coordinates
- **Data**: Float32 array of orbital values

## Configuration

### Frontend Environment Variables

- `VITE_API_URL`: Backend API URL (default: `http://localhost:8000`)

### Backend Configuration

Edit `backend/main.py` to modify:
- Molecule definition (`create_sample_molecule()`)
- MCSCF parameters
- Grid resolution defaults
- Margin size defaults

## Performance

- Target: 60fps rendering with Web Worker-based Marching Cubes
- Grid resolutions: 32 (fast), 64 (balanced), 96 (high quality)
- Binary data transfer minimizes network overhead
- Efficient GPU-based rendering with Three.js

## Mobile Support

- Touch-enabled orbit controls
- Responsive UI design
- Optimized for mobile browsers

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   Frontend      │         │    Backend       │
│   (Svelte)      │◄────────┤   (FastAPI)      │
│                 │  Binary │                  │
│ ┌─────────────┐ │  Stream │  ┌────────────┐  │
│ │ Web Worker  │ │         │  │  PySCF     │  │
│ │ (Marching   │ │         │  │  MCSCF     │  │
│ │  Cubes)     │ │         │  │  Eval      │  │
│ └─────────────┘ │         │  └────────────┘  │
│                 │         │                  │
│ ┌─────────────┐ │         │                  │
│ │ Threlte/    │ │         │                  │
│ │ Three.js    │ │         │                  │
│ └─────────────┘ │         │                  │
└─────────────────┘         └──────────────────┘
      Port 80                    Port 8000
```

## License

MIT

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.