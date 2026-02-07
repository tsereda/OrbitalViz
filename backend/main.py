from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pyscf import gto, mcscf
import numpy as np
from typing import Optional
import struct

app = FastAPI(title="PySCF MCSCF Orbital Visualization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for MCSCF results so we don't recompute for every orbital
_cached_mcscf = None


def get_mcscf_results():
    """Get cached MCSCF results (molecule + natural orbitals + occupations)"""
    global _cached_mcscf
    if _cached_mcscf is None:
        mol = create_sample_molecule()
        mf = mol.RHF().run()
        mc = mcscf.CASSCF(mf, 4, 4).run()
        natorb_coeff, ci, natorb_occ = mcscf.casci.cas_natorb(mc)
        _cached_mcscf = {
            "mol": mol,
            "mc": mc,
            "natorbs": natorb_coeff,
            "occupations": natorb_occ,
            "energy": float(mc.e_tot),
        }
    return _cached_mcscf


def create_sample_molecule():
    """Create a sample molecule for MCSCF calculation"""
    mol = gto.M(
        atom='''
        O 0.0 0.0 0.0
        H 0.0 -0.757 0.587
        H 0.0 0.757 0.587
        ''',
        basis='6-31g',
        verbose=0
    )
    return mol


def get_grid_bounds(mol, margin_angstrom=5.0):
    """Calculate grid bounds with specified margin in Angstroms"""
    coords = mol.atom_coords()
    min_coords = np.min(coords, axis=0) - margin_angstrom
    max_coords = np.max(coords, axis=0) + margin_angstrom
    return min_coords, max_coords


def evaluate_orbital_on_grid(mol, mo_coeff, grid_points):
    """Evaluate molecular orbital on grid using mol.eval_gto"""
    ao_value = mol.eval_gto('GTOval_sph', grid_points)
    mo_value = np.dot(ao_value, mo_coeff)
    return mo_value


@app.get("/")
async def root():
    return {"message": "PySCF MCSCF Orbital Visualization API"}


@app.get("/api/orbital/{orbital_index}")
async def get_orbital_data(
    orbital_index: int = 0,
    grid_size: int = 64,
    margin: float = 5.0,
    isovalue: Optional[float] = None
):
    """
    Get orbital data as Float32 binary buffer
    
    Parameters:
    - orbital_index: Index of the natural orbital to visualize
    - grid_size: Number of grid points per dimension
    - margin: Margin around molecule in Angstroms (default 5.0)
    - isovalue: Optional isovalue for reference (not used in binary stream)
    """
    # Use cached MCSCF results
    results = get_mcscf_results()
    mol = results["mol"]
    natorbs = results["natorbs"]
    
    if orbital_index >= natorbs.shape[1]:
        return Response(
            content=f"Orbital index {orbital_index} out of range",
            status_code=400
        )
    
    # Calculate grid bounds
    min_coords, max_coords = get_grid_bounds(mol, margin)
    
    # Create 3D grid
    x = np.linspace(min_coords[0], max_coords[0], grid_size)
    y = np.linspace(min_coords[1], max_coords[1], grid_size)
    z = np.linspace(min_coords[2], max_coords[2], grid_size)
    
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    grid_points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    
    # Evaluate orbital on grid
    mo_coeff = natorbs[:, orbital_index]
    orbital_values = evaluate_orbital_on_grid(mol, mo_coeff, grid_points)
    orbital_grid = orbital_values.reshape(grid_size, grid_size, grid_size)
    
    # Convert to Float32 and create binary buffer
    orbital_float32 = orbital_grid.astype(np.float32)
    binary_data = orbital_float32.tobytes()
    
    # Create metadata header (grid dimensions and bounds)
    header = struct.pack('3i6f', 
                        grid_size, grid_size, grid_size,
                        min_coords[0], min_coords[1], min_coords[2],
                        max_coords[0], max_coords[1], max_coords[2])
    
    return Response(
        content=header + binary_data,
        media_type="application/octet-stream",
        headers={
            "X-Grid-Size": str(grid_size),
            "X-Min-Coords": f"{min_coords[0]},{min_coords[1]},{min_coords[2]}",
            "X-Max-Coords": f"{max_coords[0]},{max_coords[1]},{max_coords[2]}"
        }
    )


@app.get("/api/molecule/info")
async def get_molecule_info():
    """Get information about the molecule"""
    results = get_mcscf_results()
    mol = results["mol"]
    
    return {
        "atoms": [
            {"element": atom[0], "coords": atom[1].tolist() if hasattr(atom[1], 'tolist') else list(atom[1])}
            for atom in mol._atom
        ],
        "num_orbitals": results["natorbs"].shape[1],
        "basis": mol.basis,
        "occupations": results["occupations"].tolist(),
        "energy": results["energy"],
    }


@app.get("/api/orbitals/batch")
async def get_orbital_batch(
    indices: str = "0,1,2,3",
    grid_size: int = 48,
    margin: float = 5.0,
):
    """
    Get multiple orbitals in one request as concatenated binary data.
    
    Header layout:
      - num_orbitals (1 int32)
      - grid_size x3 (3 int32)
      - bounds min/max (6 float32)
      - orbital indices (num_orbitals int32s)
    Then: num_orbitals consecutive grid blobs (each grid_size^3 float32s)
    """
    results = get_mcscf_results()
    mol = results["mol"]
    natorbs = results["natorbs"]
    
    orbital_indices = [int(i.strip()) for i in indices.split(",")]
    
    # Validate indices
    for idx in orbital_indices:
        if idx < 0 or idx >= natorbs.shape[1]:
            return Response(
                content=f"Orbital index {idx} out of range (0-{natorbs.shape[1]-1})",
                status_code=400
            )
    
    min_coords, max_coords = get_grid_bounds(mol, margin)
    
    x = np.linspace(min_coords[0], max_coords[0], grid_size)
    y = np.linspace(min_coords[1], max_coords[1], grid_size)
    z = np.linspace(min_coords[2], max_coords[2], grid_size)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    grid_points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    
    num_orbs = len(orbital_indices)
    # Header: num_orbitals, gx, gy, gz, minX, minY, minZ, maxX, maxY, maxZ, indices...
    header = struct.pack(
        f'<{4 + num_orbs}i6f',
        num_orbs, grid_size, grid_size, grid_size,
        *orbital_indices,
        float(min_coords[0]), float(min_coords[1]), float(min_coords[2]),
        float(max_coords[0]), float(max_coords[1]), float(max_coords[2]),
    )
    
    all_data = bytearray(header)
    for idx in orbital_indices:
        mo_coeff = natorbs[:, idx]
        orbital_values = evaluate_orbital_on_grid(mol, mo_coeff, grid_points)
        orbital_grid = orbital_values.reshape(grid_size, grid_size, grid_size)
        all_data.extend(orbital_grid.astype(np.float32).tobytes())
    
    return Response(
        content=bytes(all_data),
        media_type="application/octet-stream"
    )
