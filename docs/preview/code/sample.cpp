// 中文注释：C++
#include <string>
#include <vector>

template <typename T>
class 栈 {
public:
    void push(const T& v) { items_.push_back(v); }
    bool empty() const { return items_.empty(); }
private:
    std::vector<T> items_;
};
