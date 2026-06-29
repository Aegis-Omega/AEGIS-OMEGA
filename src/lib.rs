//! AEGIS-Ω Gate 206 — Constitutional Hypervisor crate root.
//!
//! Exposes the hypervisor module so its server-managed constraint enforcement
//! compiles and is testable as a standalone crate. The submodules reference
//! `crate::hypervisor::*`, so the module must be named `hypervisor` here.

pub mod hypervisor;
