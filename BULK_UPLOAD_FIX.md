# Bulk Upload Fix Summary

## Issue Identified

The bulk upload feature was failing with a **PostgreSQL sequence constraint violation** error:

```
duplicate key value violates unique constraint "visitors_visitorlog_pkey"
Key (id)=(12) already exists.
```

## Root Cause

The auto-incrementing sequence for the `VisitorLog` table (`visitors_visitorlog_id_seq`) was out of sync with the actual data in the table. This typically happens when:

1. Direct database operations bypass Django's ORM
2. Data is imported or migrated without proper sequence updates
3. The database is restored from a backup

## Solution Implemented

### 1. **Backend Improvements** (views.py)

- ✅ Improved header matching logic for Excel files

  - Now handles both exact and case-insensitive matches
  - Better error messages showing available columns
  - More flexible column name validation

- ✅ Added better error diagnostics
  - Check if worksheet has data (minimum 2 rows required)
  - Improved error handling with stack traces
  - Better logging for debugging

### 2. **Database Sequence Fix**

Created a management command to automatically fix database sequences:

```bash
python manage.py fix_sequences
```

This command:

- Finds the maximum ID in the VisitorLog table
- Sets the sequence to max_id + 1
- Prevents future constraint violations

### 3. **Testing**

Created comprehensive test script (`test_bulk_upload.py`) that:

- Creates a valid Excel file with test data
- Tests the full bulk upload workflow
- Validates response and error handling

## How to Apply the Fix

### Option 1: Use the Management Command (Recommended)

```bash
cd vms_backend
python manage.py fix_sequences
```

### Option 2: Manual SQL Fix

```sql
-- Fix VisitorLog sequence
SELECT setval('visitors_visitorlog_id_seq', (SELECT MAX(id) + 1 FROM visitors_visitorlog));
```

## Testing the Fix

Run the test script to verify bulk upload is working:

```bash
python test_bulk_upload.py
```

Expected output:

```
✅ SUCCESS!
  - Total Processed: 3
  - Successful: 3
  - Failed: 0
```

## Excel File Format Requirements

Your Excel file must have these columns (header row):

- `Name*` - Visitor name
- `Email*` - Visitor email (must be valid format)
- `Phone*` - Visitor phone number
- `Company/Organization*` - Company name
- `Visitor Type*` - professional, student, etc.
- `Visitor Category*` - industry, academic, government, other

### Example Data:

| Name\*     | Email\*          | Phone\*    | Company/Organization\* | Visitor Type\* | Visitor Category\* |
| ---------- | ---------------- | ---------- | ---------------------- | -------------- | ------------------ |
| John Doe   | test@example.com | 1234567890 | ABC Company            | Professional   | Industry           |
| Jane Smith | jane@example.com | 9876543210 | XYZ Corp               | Professional   | Industry           |

## Form Requirements

When uploading, provide these form fields:

- **Purpose**: business_meeting, interview, delivery, maintenance, training, i_factory_visit, i_factory_training, other
- **Visit Date**: YYYY-MM-DD (must be a future weekday)
- **Visit Time**: HH:MM (must be between 09:00 and 17:00)
- **Host Name**: The person hosting the visitors
- **Host Email**: Valid email address of the host

## Validation Rules

The bulk upload endpoint validates:

1. ✅ File is not empty
2. ✅ File is valid Excel (.xlsx or .xls)
3. ✅ All required columns are present
4. ✅ Email format is valid
5. ✅ Visit date is not in the past
6. ✅ Visit date is a weekday (Mon-Fri)
7. ✅ Visit time is during business hours (09:00-17:00)
8. ✅ Host email is valid
9. ✅ No more than 20 visitors per upload
10. ✅ Available capacity exists for the requested time slot

## Performance

The endpoint is optimized for bulk operations:

- Uses `bulk_create()` for database inserts (much faster)
- Sends emails asynchronously via Celery
- Processes multiple visitors in a single request
- Returns detailed success/failure information per visitor

## Future Improvements

1. Consider adding automatic sequence reset after bulk operations
2. Add more flexible visitor type/category mappings
3. Implement partial upload support (skip invalid rows, upload valid ones)
4. Add progress tracking for large uploads

## Support

If you encounter any issues:

1. Check the error message for specific validation failures
2. Run `python manage.py fix_sequences` to fix any sequence issues
3. Check server logs for detailed error traces
4. Use the test script to validate your Excel file format
