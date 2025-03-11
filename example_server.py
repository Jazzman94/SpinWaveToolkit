import SpinWaveToolkit as SWT

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# pip install streamlit
# streamlit run example_server.py

# Hlavní titulek
st.title("SpinWaveToolkit App Example")

st.text("Here is an example of code")

kxi = np.linspace(0.5e6, 3e6, 150)

# Degeneration of the 00 and 22 mode in CoFeB
n = st.slider("Select n", min_value=0, max_value=5, value=0)
nc = st.slider("Select nc", min_value=0, max_value=5, value=2)

MagnetronCoFeB = SWT.Material(Aex = 13.5e-12, Ms = 1.24e6, gamma = 30.8*2*np.pi*1e9, alpha = 5e-3)
CoFeBchar = SWT.SingleLayer(kxi = kxi, theta = np.pi/2, phi = np.deg2rad(90), d = 100e-9, boundary_cond = 4, dp = 1e6, Bext = 0.08, material = MagnetronCoFeB)
w00 = CoFeBchar.GetDispersion(n=n)*1e-9/(2*np.pi)
w22 = CoFeBchar.GetDispersion(n=nc)*1e-9/(2*np.pi)
[wd02, wd20] =  [w*1e-9/(2*np.pi) for w in CoFeBchar.GetSecondPerturbation(n=n, nc=nc)]

code = """
kxi = np.linspace(0.5e6, 3e6, 150)
MagnetronCoFeB = SWT.Material(Aex = 13.5e-12, Ms = 1.24e6, gamma = 30.8*2*np.pi*1e9, alpha = 5e-3)
CoFeBchar = SWT.SingleLayer(kxi = kxi, theta = np.pi/2, phi = np.deg2rad(90), d = 100e-9, boundary_cond = 4, dp = 1e6, Bext = 0.08, material = MagnetronCoFeB)
w00 = CoFeBchar.GetDispersion(n=n)*1e-9/(2*np.pi)
w22 = CoFeBchar.GetDispersion(n=nc)*1e-9/(2*np.pi)

[wd02, wd20] =  [w*1e-9/(2*np.pi) for w in CoFeBchar.GetSecondPerturbation(n=n, nc=nc)]
"""
st.code(code, language='python')   

fig, ax = plt.subplots()
ax.plot(kxi*1e-6, w00, label=f'{n}{n}')
ax.plot(kxi*1e-6, w22, label=f'{nc}{nc}')
ax.plot(kxi*1e-6, wd02, label=f'{n}{nc}')
ax.plot(kxi*1e-6, wd20, label=f'{nc}{n}')
ax.set_xlabel('kxi (rad/um)')
ax.set_ylabel('Frequency (GHz)')
ax.legend()
ax.set_title('Dispersion relation of degenerate modes in CoFeB, dp = {:.2e}'.format(CoFeBchar.dp))
st.pyplot(fig)









