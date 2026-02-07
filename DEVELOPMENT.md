# Development Notes

## Architecture Overview

This application implements a decoupled microservices architecture for PySCF MCSCF orbital visualization:

### Backend (FastAPI)
- **Technology**: Python 3.11+, FastAPI, PySCF, NumPy
- **Port**: 8000
- **Key Features**:
  - Evaluates natural orbitals from MCSCF calculations
  - Generates 3D grids with configurable margins (default 3Å)
  - Uses PySCF's `mol.eval_gto()` for efficient orbital evaluation
  - Streams binary data (Float32) with minimal overhead
  - Header format: 3 ints (grid dims) + 6 floats (bounds) = 36 bytes

### Frontend (Svelte + Threlte)
- **Technology**: Svelte 5, Vite, Threlte (Three.js wrapper)
- **Port**: 5173 (dev), 80 (production)
- **Key Features**:
  - Web Worker-based Marching Cubes for non-blocking isosurface extraction
  - Real-time isovalue adjustment with sliders
  - OrbitControls for mouse/touch interaction
  - Responsive design with mobile-friendly controls
  - Grid resolution options: 32 (fast), 64 (balanced), 96 (high quality)

## Performance Considerations

### Backend
- MCSCF calculation is performed once per molecule
- Grid evaluation scales as O(n³) where n is grid resolution
- Binary streaming is faster than JSON serialization
- Consider caching calculated grids for repeated requests

### Frontend
- Web Worker prevents UI blocking during Marching Cubes
- Target: 60fps rendering (achieved with Three.js GPU acceleration)
- Large grid sizes (96+) may impact performance on mobile devices
- Consider implementing progressive loading for very high resolutions

## Known Limitations

1. **Marching Cubes Implementation**: The current implementation uses a simplified triangle table. For production use, implement the full 256-case table.

2. **Orbital Selection**: Currently limited to natural orbitals from CASSCF. Can be extended to support:
   - Molecular orbitals (MOs)
   - Natural transition orbitals (NTOs)
   - Density matrices

3. **Molecule Input**: Hardcoded water molecule. Future improvements:
   - Upload molecule files (XYZ, MOL, etc.)
   - Web-based molecule editor
   - Integration with molecular databases

## Deployment on NRP Nautilus

The application is designed for Kubernetes deployment:

```bash
# Build Docker images
docker build -t registry.nrp-nautilus.io/your-namespace/orbitalviz-backend:latest backend/
docker build -t registry.nrp-nautilus.io/your-namespace/orbitalviz-frontend:latest frontend/

# Push to registry
docker push registry.nrp-nautilus.io/your-namespace/orbitalviz-backend:latest
docker push registry.nrp-nautilus.io/your-namespace/orbitalviz-frontend:latest

# Update image references in k8s/*.yaml files

# Deploy
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
```

## API Usage Examples

### Get Molecule Info
```bash
curl http://localhost:8000/api/molecule/info
```

Response:
```json
{
  "atoms": [
    {"element": "O", "coords": [0.0, 0.0, 0.0]},
    {"element": "H", "coords": [0.0, -1.43, 1.11]},
    {"element": "H", "coords": [0.0, 1.43, 1.11]}
  ],
  "num_orbitals": 13,
  "basis": "6-31g"
}
```

### Get Orbital Data
```bash
curl http://localhost:8000/api/orbital/0?grid_size=64&margin=3.0 -o orbital.bin
```

Binary format:
- Header: 36 bytes (3 int32 + 6 float32)
- Data: grid_size³ × 4 bytes (float32 values)

## Future Enhancements

1. **Backend**:
   - Add caching layer (Redis/Memcached)
   - Support multiple molecules simultaneously
   - Implement electron density visualization
   - Add support for excited states

2. **Frontend**:
   - Add animation/rotation controls
   - Multiple isosurface colors for positive/negative lobes
   - Export to STL/OBJ for 3D printing
   - Screenshot/video capture functionality
   - VR/AR support

3. **DevOps**:
   - Add CI/CD pipeline
   - Implement health checks and metrics (Prometheus)
   - Add logging aggregation (ELK stack)
   - Set up monitoring and alerting

## Testing

Run the test suite:
```bash
./test.sh
```

For manual testing:
```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm install
npm run dev

# Open browser to http://localhost:5173
```

## Troubleshooting

### Backend Issues
- **PySCF import error**: Install with `pip install pyscf`
- **MCSCF convergence**: Adjust initial guess or active space
- **Memory errors**: Reduce grid size or switch to sparse grids

### Frontend Issues
- **Black screen**: Check browser console for WebGL errors
- **Performance issues**: Reduce grid resolution or disable shadows
- **Worker errors**: Ensure marchingCubes.worker.js is properly bundled

## References

- PySCF Documentation: https://pyscf.org/
- Threlte Documentation: https://threlte.xyz/
- Marching Cubes Algorithm: Paul Bourke's implementation
- NRP Nautilus: https://nautilus.optiputer.net/
