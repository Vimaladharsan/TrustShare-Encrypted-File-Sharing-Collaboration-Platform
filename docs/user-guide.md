# TrustShare – User Guide

How to use TrustShare, for **users** (part 1) and **administrators** (part 2). The screenshots use
demo data.

**Contents**

- Part 1 – Users: [Getting started](#1-getting-started) · [Files and folders](#2-files-and-folders) ·
  [Sharing](#3-sharing) · [Files shared with you](#4-files-shared-with-you) ·
  [Secure vault](#5-secure-vault) · [Notifications](#6-notifications) ·
  [Analytics and activity](#7-analytics-and-activity) · [Account and security](#8-account-and-security) ·
  [Appearance](#9-appearance-and-phones)
- Part 2 – Administrators: [The admin console](#10-the-admin-console) ·
  [Monitoring](#11-monitoring-activity-and-audit-logs) · [Alerts](#12-security-and-suspicious-activity) ·
  [Reports and analytics](#13-reports-and-analytics) · [Users and system](#14-users-notifications-and-system)

---

# Part 1 – Users

## 1. Getting started

![Landing page](screenshots/01-landing-page.png)

1. Open TrustShare and choose **Get started** to create an account (name, email, password), or
   **Log in**. The password needs at least 10 characters with upper and lower case, a digit and a
   symbol – the form shows which rules are met as you type.
2. Confirm your email with the link we send you.
3. You can also **Continue with Google**.

![Sign in](screenshots/02-sign-in.png)

If two-step verification is on, TrustShare asks for the 6-digit code from your authenticator app
after the password. Forgot your password? Use **Forgot password?** – a reset link valid for 15
minutes is emailed to you.

After signing in you land on the **Dashboard**: storage used, recent uploads, downloads and shares,
your recent files and shortcuts.

![Dashboard](screenshots/03-dashboard.png)

## 2. Files and folders

![My Files](screenshots/04-my-files.png)

**My Files** shows your folders as cards and your files in a table. Click a column header to sort,
use the chips (Documents, Spreadsheets, Presentations, Images, Text) to filter, and the search box
at the top to find a file in any folder.

**Folders** – *New folder* creates one; click a folder to open it. The breadcrumb above the title
(*My Files › Projects*) takes you back up.

![Folder with breadcrumbs](screenshots/05-folder-and-breadcrumbs.png)

**Upload** – click *Upload* and drop files or browse. You can upload several at once and watch the
progress of each. Allowed: PDF, Word, Excel, PowerPoint, text, CSV, PNG and JPG, up to 25 MB. A file
whose content doesn't match its extension (for example a program renamed to `.pdf`) is refused. If
you upload the same file twice you can choose *Keep both*.

![Upload dialog](screenshots/06-upload-dialog.png)

Every uploaded file is encrypted with its own key before it is stored.

**Open and act on a file** – click a file's name to preview it (PDF, images and text). The **⋮**
menu next to a file offers Preview, Download, Add to favorites, Share, Rename, Move to…, Move to
vault and Move to trash.

![File preview](screenshots/07-file-preview.png)

**Move by drag and drop** – drag a file onto a folder card, or onto a breadcrumb such as *My Files*.

**Several files at once** – tick the boxes to select files. A toolbar appears: download them as one
ZIP, share them, move them, or move them to trash.

![Multi-select](screenshots/10-multi-select.png)

**Trash** – trashed files and folders can be restored, or deleted forever. *Empty trash* removes
everything in it. Trashed files still count toward your storage until deleted.

**Favorites** and **Recent** list your starred files and the files you worked on lately; **Storage**
shows what uses your space.

## 3. Sharing

Open a file's **⋮ → Share** (or select several files, or use a folder's **⋮ → Share**).

![Share dialog](screenshots/08-share-dialog.png)

Choose who gets access:

- **Anyone with the link** – no account needed. Set:
  - **Permission:** *View only* (preview in the browser) or *View & download*
  - **Expires after:** from 1 hour to 30 days, or an exact date and time
  - **Download limit** (optional): the link stops after that many downloads
  - **Protect with a password** (optional): visitors must enter it first
- **Specific people** – enter the email of a registered user; they see it under *Shared with me*
  and get a notification and an email.

Click **Create link**. Copy the link – it is shown only once, because TrustShare stores only a
fingerprint of it. A **QR code** is shown too, for opening the link on a phone.

![Link created with QR code](screenshots/09-share-link-with-qr-code.png)

**Shared by me** lists everything you shared, with its permission, expiry, downloads and status.

![Shared by me](screenshots/11-shared-by-me.png)

- **Edit** – change permission, expiry or download limit; the link stays the same.
- **History** (clock icon) – who opened the link, viewed or downloaded the file, when and from which
  device, and refused attempts with the reason (expired, revoked, wrong password …).
- **Revoke** – the link stops working immediately.

![Access history](screenshots/12-access-history.png)

**What a visitor sees** – the file name, size, what they may do, when the link expires and how many
downloads are left. The file is decrypted only while it is sent to them.

![Public share page](screenshots/13-public-share-link.png)

## 4. Files shared with you

**Shared with me** lists files other people shared with you, who shared them, what you may do and
when access ends. Preview or download from here.

![Shared with me](screenshots/14-shared-with-me.png)

## 5. Secure vault

For your most sensitive files. The vault has its own password (different from your login password),
and its files get an extra layer of encryption – without the vault password nobody can open them,
not even the server's administrators.

![Secure vault](screenshots/15-secure-vault.png)

1. Open **Secure vault** and set a vault password.
2. Enter it to unlock the vault, then **Add files**, or move a file in with **⋮ → Move to vault**.
3. The password is asked for every action and never stored. Five wrong attempts lock the vault for
   15 minutes.

Vault files are private: they can't be shared and don't appear in search or Recent. If you forget
the vault password, the vault can only be reset – its files are then gone for good.

## 6. Notifications

The **bell** in the top bar shows new notifications instantly: a file shared with you, your shared
file was downloaded, a link is about to expire or has expired, and security warnings such as a
sign-in from a new device.

![Notification bell](screenshots/19-notification-bell.png)

**Notifications** shows them all, with filters and *Mark all read*. In **Settings → Notifications**
choose which ones are also sent by email, and turn on desktop pop-ups for this device.

![Notifications page](screenshots/18-notifications.png)

## 7. Analytics and activity

**File Analytics** shows your storage by file type, uploads over time, downloads (including how many
different people downloaded your shared files) and sharing activity, for a date range you choose.

![File analytics](screenshots/16-file-analytics.png)

**Activity Logs** lists everything done with your account – sign-ins, uploads, downloads, shares –
with IP address and time. Entries can't be edited or deleted.

![Activity log](screenshots/17-activity-log.png)

**Security** explains how your files and account are protected.

![Security overview](screenshots/23-security-overview.png)

## 8. Account and security

Open **Settings** from the sidebar or the account menu (click your name).

**Profile** – your **security score** (0–100) with a checklist; each missing item has a *Fix now*
button. Below it you can edit your name. The strip under your name shows member since, files,
storage, active shares and your previous sign-in.

![Account security score](screenshots/20-account-security-score.png)

**Security** – turn on **two-step verification**: scan the QR code with Google Authenticator (or a
similar app), enter a code, and save the 10 backup codes somewhere safe. Change your password here
too – other devices are signed out.

![Two-step verification](screenshots/21-two-step-verification.png)

**Devices** – every device signed in to your account. Don't recognise one? **Sign out** that device
(it loses access immediately) and change your password. *Log out of all devices* ends every session.
When TrustShare notices a sign-in from a new device it notifies you, and the notification opens this
page with a *Was this sign-in you?* check.

![Signed-in devices](screenshots/22-signed-in-devices.png)

**Account** – delete your account. This erases all your files, keys, shares and sessions and can't
be undone.

## 9. Appearance and phones

Switch between light and dark mode with the moon / sun button in the top bar, or choose *Light*,
*Dark* or *System* in the account menu.

![Dark mode](screenshots/24-dark-mode.png)

TrustShare works on phones: the sidebar folds into a menu. Drag and drop isn't available on touch
screens – use **⋮ → Move to…** instead.

<img src="screenshots/25-phone-layout.png" alt="Phone layout" width="320">

---

# Part 2 – Administrators

## 10. The admin console

Admins open it from the account menu → **Admin panel**. It has its own dark look so admin mode is
never confused with the workspace; *Back to my workspace* returns.

**Privacy by design:** admins see accounts, sizes, file IDs and security events – **never the names
or contents of users' files**.

The **Dashboard** summarises users, encrypted storage, active shares, security events, platform
activity, accounts by role and the encryption keys in use.

![Admin dashboard](screenshots/30-admin-dashboard.png)

## 11. Monitoring: activity and audit logs

**User activity** – every recorded action (sign-ins, uploads, downloads, shares, denied attempts)
with filters by user, activity type and status. *Live* shows new actions as they happen.

![User activity monitoring](screenshots/31-admin-user-activity.png)

**Audit logs** – the permanent record. Each entry is chained to the previous one with a SHA-256
hash; the green **Integrity verified** banner confirms nothing was changed or deleted. Filter by
user, activity type, file ID, status and date, and **Export CSV**.

![Audit logs](screenshots/32-admin-audit-logs.png)

## 12. Security and suspicious activity

**Security monitoring** – sign-in success and failure, unauthorized and blocked attempts, security
events by severity, and recent events.

![Security monitoring](screenshots/33-admin-security-monitoring.png)

**Suspicious activity** – alerts raised automatically, for example more than 5 failed sign-ins on
one account in 10 minutes, repeated access without permission, more than 20 downloads in 5 minutes,
or repeated use of expired or revoked links. Every admin is notified.

![Suspicious activity alerts](screenshots/34-admin-suspicious-activity.png)

Click **Review** on an alert to see its details:

- **Activity around this time** – everything that user (or IP address) did from 30 minutes before
  to 30 minutes after the alert.
- **Acknowledge** – you are looking into it.
- **Resolve** – add a note (what you found) and close it. Every step is recorded in the audit log.

![Alert review](screenshots/35-admin-alert-review.png)

If an account was locked by repeated wrong passwords, unlock it under **User management**.

## 13. Reports and analytics

**File activity reports** – uploads, downloads, sharing, one user's activity and security, each with
totals, a chart and a table. Filter by date range, user, file type and file ID; **Export CSV**.

![File activity reports](screenshots/36-admin-reports.png)

![Sharing report](screenshots/38-admin-sharing-reports.png)

**Storage analytics** – total storage, storage per user, uploads by date and file type, downloads and
sharing across the platform.

![Storage analytics](screenshots/37-admin-storage-analytics.png)

## 14. Users, notifications and system

**User management** – search accounts, change a role (Admin, User, Guest), **Disable** an account
(it is signed out everywhere), **Unlock** a locked account. Accounts that haven't signed in for 30+
days can be **deleted** together with their files. You can't change or delete your own account or
the last admin.

![User management](screenshots/40-admin-user-management.png)

**Notifications** – how many notifications and emails were sent, by type, and your own security
alert inbox.

![Notification management](screenshots/39-admin-notification-management.png)

**System monitoring** – the status of PostgreSQL, MongoDB, Redis and object storage, and the
encryption keys (which master key is active and how many file keys use it).

![System monitoring](screenshots/41-admin-system.png)
