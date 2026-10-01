# Delete local data and remove Google access

de-Mail Desktop does not keep Gmail data on a Liminal server. All application data is controlled
on the person's Windows computer.

## Disconnect Google

Open Settings and select **Disconnect Google account**. This removes the encrypted local OAuth
credential. It does not delete archives, Gmail messages, or the OAuth client configuration.

To remove the grant at Google as well, open the
[Google Account connections page](https://myaccount.google.com/connections), select de-Mail
Desktop, and remove its access.

## Reset authorization

Open Settings and select **Reset authorization**. This removes the encrypted local OAuth
credential and resets the first-run privacy acknowledgement. A development build also forgets
its manually selected OAuth client file. The next connection begins at the first-run disclosure.

## Delete archives and application history

Archive folders are ordinary folders at the location selected during archiving. Delete them
with Windows file management only after confirming that deletion is intended and any required
backup exists.

Local application history is stored under `%LOCALAPPDATA%\de-Mail Desktop`. Uninstalling the
application deliberately leaves this data in place so upgrades do not destroy history. A person
who wants a complete local removal can uninstall the application and then delete that folder.

Questions can be sent to alex@liminalmemory.com. Liminal cannot delete data it never receives.
