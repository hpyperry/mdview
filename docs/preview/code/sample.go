// 中文注释：Go
package main

import "fmt"

type 服务器 struct {
	名称 string
	端口 int
}

func main() {
	s := 服务器{名称: "mdview", 端口: 8000}
	fmt.Printf("%s:%d\n", s.名称, s.端口)
}
