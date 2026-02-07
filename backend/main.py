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


def get_grid_bounds(mol, margin_angstrom=3.0):
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
    margin: float = 3.0,
    isovalue: Optional[float] = None
):
    """
    Get orbital data as Float32 binary buffer
    
    Parameters:
    - orbital_index: Index of the natural orbital to visualize
    - grid_size: Number of grid points per dimension
    - margin: Margin around molecule in Angstroms (default 3.0)
    - isovalue: Optional isovalue for reference (not used in binary stream)
    """
    # Create molecule and run MCSCF
    mol = create_sample_molecule()
    mf = mol.RHF().run()
    mc = mcscf.CASSCF(mf, 4, 4).run()
    
    # Get natural orbitals
    natorbs = mc.mo_coeff
    
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
    mol = create_sample_molecule()
    mf = mol.RHF().run()
    mc = mcscf.CASSCF(mf, 4, 4).run()
    
    return {
        "atoms": [
            {"element": atom[0], "coords": atom[1].tolist()}
            for atom in mol._atom
        ],
        "num_orbitals": mc.mo_coeff.shape[1],
        "basis": mol.basis
    }
