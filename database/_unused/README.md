# Not part of the install

These three files were found inside `myv_myTickets/` but do not belong to the current design.
They are kept here only so nothing is lost. `install_all.sql` does not run them.

| File | Why it is not used |
|---|---|
| `main__trg_admin_bi.sql` | A trigger on the `admin` table. That table lives in `myv_myTickets_admin`, so this copy fails in the main database. The real one is `myv_myTickets_admin/trigger/trg_admin_bi.sql`. |
| `main__pc_add_event.sql` | The first version of `pc_add_event`, from before the admin database existed (no admin check, no audit log). Replaced by `myv_myTickets_admin/procedure/pc_add_event.sql`. |
| `main__pc_event_stats.sql` | Same story: replaced by `myv_myTickets_admin/procedure/pc_event_stats.sql`. No account is granted EXECUTE on it. |

If your live database still has the two old procedures in `myv_myTickets`, they are harmless
(no app account can call them). To remove them:

```sql
DROP PROCEDURE IF EXISTS myv_myTickets.pc_add_event;
DROP PROCEDURE IF EXISTS myv_myTickets.pc_event_stats;
```
