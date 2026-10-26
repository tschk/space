// Synthetic compiler corpus: real owned malloc/memcpy over Linux mmap.
static mut CALLS:i64=0;
fn values()->[i64;3] {
    unsafe{CALLS=CALLS+1;}
    [20,22,7]
}
fn main()->i64 {
    let original=values();
    let mut copy=original;
    copy[0]=99;
    copy[2]=11;
    if original[0]!=20 || original[1]!=22 || original[2]!=7{return 1;}
    if copy[0]!=99 || copy[1]!=22 || copy[2]!=11{return 2;}
    if unsafe{CALLS}!=1{return 3;}
    original[0]+original[1]
}
