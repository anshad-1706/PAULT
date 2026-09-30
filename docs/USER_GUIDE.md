# PAULT User Guide

This guide covers the Windows x64 portable application. The downloadable `PAULT.exe` is for Windows; it is not a macOS, Linux, or mobile app.

## A Few Terms

- **PAULT** is the application you use to open and manage your protected files.
- A **vault** is encrypted storage for your files.
- **PAULT.exe** is the application file you open on Windows.
- A **`.pault` vault** is a folder whose name ends in `.pault`. It contains the vault data; it is not one standalone document file.

## First-Time Setup

1. **Download PAULT.** Open the [official PAULT GitHub Releases](https://github.com/anshad-1706/PAULT/releases) page, download `PAULT-v1.0.0-windows-x64.zip`, and extract the ZIP. Keep the extracted `PAULT` folder together. Its contents include:

   ```text
   PAULT/
   ├── PAULT.exe
   ├── _internal/
   └── Vaults/
   ```

   Do not separate `PAULT.exe` from `_internal`.

2. **Copy PAULT to a USB drive.** Connect the USB drive to your Windows computer and copy the complete `PAULT` folder to it. For example:

   ```text
   E:\
   └── PAULT\
       ├── PAULT.exe
       ├── _internal\
       └── Vaults\
   ```

   `E:` is only an example. Windows may assign the USB a different letter, such as `D:`, `F:`, or another letter. Keep the complete application folder together.

3. **Open PAULT.** Open the `PAULT` folder on the USB and double-click `PAULT.exe`. PAULT runs as a portable application and does not require a traditional Windows installation.

4. **Create your first vault.** On the welcome screen, choose **Create New Vault**. Enter a vault name and choose where it should be stored. PAULT initially suggests the `Vaults` folder beside the portable app, but you may choose another accessible location, including a location outside the USB. The app displays the final destination before creation. For example:

   ```text
   E:\PAULT\Vaults\Personal.pault
   ```

   `Personal` and `E:` are examples only. You can choose another name or location, and the drive letter may differ on another computer. Choose **Create Vault** when the destination is correct.

5. **Create a password.** Enter a strong password and confirm it. Choose a password you can securely remember, and do not share it. PAULT has no password recovery service; if you lose the password, the encrypted vault may become inaccessible. Complete the acknowledgement in the dialog and create the vault. PAULT opens the new vault for use.

6. **Add files.** In the vault, choose **+ Add Files** or drag files into PAULT. You can add photos, videos, documents, and other files. To add a folder, drag it into PAULT. Confirm the import when asked. Importing does not automatically delete or securely erase the original files outside PAULT.

7. **Organize with folders.** Choose **+ New Folder** to create a folder inside the vault. For example:

   ```text
   Personal
   ├── Photos
   ├── Videos
   ├── Documents
   └── Private
   ```

8. **Lock PAULT when finished.** Choose **Lock Vault**. The vault remains encrypted on storage, and opening it again requires its password. PAULT also has a configurable inactivity auto-lock; its setting is available under **Security Settings**.

9. **Eject the USB safely.** Wait for any import, export, or other operation to finish. Lock PAULT, close it, then use Windows **Safely Remove Hardware / Eject** before physically disconnecting the USB. PAULT checks for unavailable vault storage while running, but this does not replace normal safe-eject behavior.

## If You Already Have a Vault

1. Open `PAULT.exe`.
2. Choose **Open Existing Vault**.
3. In the folder picker titled **Open PAULT Vault**, select the `.pault` vault folder.
4. Enter the vault password and choose **Unlock**.
5. Use the files and folders in the vault normally.

## Using PAULT on Another Windows Computer

1. Connect the USB drive to the other Windows computer.
2. Open the `PAULT` folder on the USB and run `PAULT.exe`.
3. Choose **Open Existing Vault**, select the existing `.pault` folder, and enter its password.
4. Use the vault normally, then lock PAULT and safely eject the USB when finished.

The USB drive letter can change between computers. For example, the PAULT folder might be under `E:\PAULT` on one computer and `F:\PAULT` on another. No particular drive letter is required. If the vault is not in the suggested `Vaults` folder, browse to its current location.

## Export a File

To make a copy outside PAULT, select the file or folder and choose **Export**. Choose a destination and confirm the export. Exported files outside the vault are ordinary plaintext files and are no longer protected by PAULT's encrypted vault. PAULT does not automatically encrypt exported copies.

## Important Safety Notes

- Keep the entire `PAULT` application folder together. Do not rename or delete required application files.
- Do not disconnect the USB while PAULT is actively writing data.
- Lock PAULT and use Windows safe eject before removing the USB.
- Keep a separate backup of important encrypted vaults; PAULT does not automatically create backups.
- Remember your vault password and do not share it. PAULT cannot recover a forgotten password.
- Imported originals outside PAULT are not automatically deleted.

## Complete First-Time Workflow

```text
USB
  ↓
Open PAULT.exe
  ↓
Create New Vault
  ↓
Choose Location and Vault Name
  ↓
Create Password
  ↓
Use the New Vault
  ↓
Add Files / Folders
  ↓
Organize Files
  ↓
Lock Vault
  ↓
Safely Eject USB
```

## Plaintext and Other Limitations

PAULT cannot guarantee that plaintext never exists temporarily outside the vault. The operating system and other applications may create memory, cache, or temporary copies. Video playback uses a temporary plaintext file for the system media player, and cleanup cannot guarantee forensic erasure. Exported files are plaintext copies outside the vault. Keep independent backups of important data.