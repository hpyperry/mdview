// 中文注释：Rust
use std::collections::HashMap;

fn main() {
    let mut 映射: HashMap<u64, String> = HashMap::new();
    映射.insert(1, String::from("中文"));
    for (k, v) in &映射 {
        println!("{} => {}", k, v);
    }
}
