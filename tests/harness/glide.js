// A stand-in for the few Glide APIs the compiled business rules use, so the script the platform will run can be
// run here, against the same cases the Python replay engine decides. Reads {script, users, cases} on stdin;
// writes, per case, the approvers the script inserted and any error message it raised.
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));

function GlideDateTime() {
  this.d = new Date();
  this.setValueUTC = (s) => { this.d = new Date(s.replace(' ', 'T') + 'Z'); };
  this.getYearUTC = () => this.d.getUTCFullYear();
  this.getMonthUTC = () => this.d.getUTCMonth() + 1;
  this.getDayOfMonthUTC = () => this.d.getUTCDate();
}

function makeGlideRecord(users, inserted) {
  return function GlideRecord(table) {
    this.table = table; this.q = []; this.rows = []; this.i = -1; this.f = {};
    this.addQuery = (k, v) => { this.q.push([k, v]); };
    this.addActiveQuery = () => {};
    this.orderBy = () => {};
    this.initialize = () => { this.f = {}; };
    this.query = () => {
      this.rows = table === 'sys_user' ? users.filter(u => this.q.every(([k, v]) => u[k] === v)) : [];
      this.i = -1;
    };
    this.next = () => { this.i += 1; if (this.i < this.rows.length) { Object.assign(this, this.rows[this.i]); return true; } return false; };
    this.insert = () => { if (table === 'sysapproval_approver') inserted.push({ approver: this.approver, comments: this.comments }); };
  };
}

const out = [];
for (const c of input.cases) {
  const inserted = [], errors = [];
  const current = {
    sys_id: 'ritm', variables: c.variables || {},
    getValue: (f) => (c.fields[f] === undefined ? '' : String(c.fields[f])),
    setValue: (f, v) => { c.fields[f] = v; }, setAbortAction: () => { errors.push('abort'); },
  };
  const gs = { addErrorMessage: (m) => errors.push(m) };
  const GlideRecord = makeGlideRecord(input.users, inserted);
  new Function('current', 'previous', 'GlideRecord', 'GlideDateTime', 'gs', input.script)(current, null, GlideRecord, GlideDateTime, gs);
  out.push({ approvers: inserted.map(a => a.approver), errors });
}
process.stdout.write(JSON.stringify(out));
